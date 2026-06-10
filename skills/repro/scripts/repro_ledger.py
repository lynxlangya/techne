#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


TAIL_LINES = 50
TAIL_BYTES = 8192
CONTEXT_LINES = 2
CONTEXT_BYTES = 1024


ANSI_RE = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]"
    r"|\x1b\][^\x07]*(?:\x07|\x1b\\)"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip(".-_")
    return slug or "bug"


def require_posix() -> None:
    if os.name != "posix" or not hasattr(os, "killpg"):
        raise SystemExit(
            "repro_ledger.py v1 supports POSIX developer environments only "
            "(macOS/Linux). Windows support is a recorded coverage gap."
        )


def resolve_project(value: Path) -> Path:
    project = value.resolve()
    if not project.is_dir():
        raise SystemExit(f"Project directory does not exist: {project}")
    return project


def resolve_cwd(project: Path, cwd_value: str) -> tuple[Path, str]:
    raw = Path(cwd_value)
    if raw.is_absolute():
        raise SystemExit("--cwd must be project-relative, not absolute")
    normalized = Path(os.path.normpath(cwd_value))
    if str(normalized) == ".":
        rel = "."
    elif str(normalized).startswith("../") or str(normalized) == "..":
        raise SystemExit("--cwd must stay inside the project root")
    else:
        rel = normalized.as_posix()
    target = (project / rel).resolve()
    try:
        target.relative_to(project)
    except ValueError as exc:
        raise SystemExit(f"--cwd escapes the project root: {cwd_value}") from exc
    if not target.is_dir():
        raise SystemExit(f"--cwd directory does not exist: {rel}")
    return target, rel


def ensure_gitignore(project: Path) -> None:
    gitignore = project / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    if ".techne/" not in [line.strip() for line in existing]:
        prefix = "" if not existing or existing[-1] == "" else "\n"
        with gitignore.open("a", encoding="utf-8") as handle:
            handle.write(f"{prefix}.techne/\n")


def ledger_path(project: Path, bug: str) -> Path:
    return project / ".techne" / "repro" / f"{slugify(bug)}.jsonl"


def read_entries(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSONL in {path}:{lineno}: {exc}") from exc
    return entries


def append_entry(project: Path, bug: str, entry: dict) -> Path:
    ensure_gitignore(project)
    path = ledger_path(project, bug)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def normalize_output(value: str) -> str:
    stripped = ANSI_RE.sub("", value)
    return stripped.replace("\r\n", "\n").replace("\r", "\n")


def output_tail(raw: str) -> str:
    lines = raw.splitlines()[-TAIL_LINES:]
    tail = "\n".join(lines)
    encoded = tail.encode("utf-8", errors="replace")
    if len(encoded) > TAIL_BYTES:
        tail = encoded[-TAIL_BYTES:].decode("utf-8", errors="replace")
    return tail


def expect_context(normalized_output: str, normalized_expect: str) -> str:
    if not normalized_expect:
        return ""
    index = normalized_output.find(normalized_expect)
    if index < 0:
        return ""
    line_start = normalized_output.rfind("\n", 0, index) + 1
    line_no = normalized_output.count("\n", 0, line_start)
    lines = normalized_output.splitlines()
    start = max(0, line_no - CONTEXT_LINES)
    end = min(len(lines), line_no + CONTEXT_LINES + 1)
    snippet = "\n".join(lines[start:end])
    encoded = snippet.encode("utf-8", errors="replace")
    if len(encoded) > CONTEXT_BYTES:
        snippet = encoded[:CONTEXT_BYTES].decode("utf-8", errors="replace")
    return snippet


def git_text(project: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def git_evidence(project: Path) -> dict | None:
    try:
        inside = git_text(project, ["rev-parse", "--is-inside-work-tree"]).strip()
        if inside != "true":
            return None
        head = git_text(project, ["rev-parse", "HEAD"]).strip()
        branch = git_text(project, ["branch", "--show-current"]).strip() or "DETACHED"
        status = git_text(project, ["status", "--porcelain"])
        tracked_diff = git_text(project, ["diff", "HEAD"])
        return {
            "head": head,
            "branch": branch,
            "dirty": bool(status.strip()),
            "statusPorcelainHash": sha256_text(status),
            "trackedDiffHash": sha256_text(tracked_diff),
        }
    except Exception:
        return None


def shell_command(argv: list[str]) -> str:
    return " ".join(argv)


def build_identity(args: argparse.Namespace, rel_cwd: str, command: list[str]) -> dict:
    if args.shell:
        return {
            "mode": "shell",
            "shellCommand": shell_command(command),
            "cwd": rel_cwd,
            "timeoutSec": args.timeout,
        }
    return {
        "mode": "argv",
        "argv": command,
        "cwd": rel_cwd,
        "timeoutSec": args.timeout,
    }


def display_command(args: argparse.Namespace, command: list[str]) -> str:
    if args.shell:
        return shell_command(command)
    return shlex.join(command)


def run_probe(args: argparse.Namespace) -> None:
    require_posix()
    project = resolve_project(args.project)
    run_cwd, rel_cwd = resolve_cwd(project, args.cwd)
    command = args.command
    if not command:
        raise SystemExit("run requires a command after --")

    identity = build_identity(args, rel_cwd, command)
    start = time.monotonic()
    timed_out = False
    exit_code: int | None = None
    output = ""
    process = subprocess.Popen(
        shell_command(command) if args.shell else command,
        cwd=run_cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=args.shell,
        executable="/bin/sh" if args.shell else None,
        start_new_session=True,
    )
    try:
        output, _ = process.communicate(timeout=args.timeout)
        exit_code = process.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(process.pid, signal.SIGTERM)
            output, _ = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            output, _ = process.communicate()
        exit_code = process.returncode
    duration_ms = int((time.monotonic() - start) * 1000)

    normalized_output = normalize_output(output)
    normalized_expect = normalize_output(args.expect) if args.expect is not None else None
    expect_matched = None
    context = ""
    if normalized_expect is not None:
        expect_matched = normalized_expect in normalized_output
        if expect_matched:
            context = expect_context(normalized_output, normalized_expect)

    entry = {
        "ts": utc_now(),
        "type": "run",
        "identity": identity,
        "displayCommand": display_command(args, command),
        "exit": exit_code,
        "timedOut": timed_out,
        "durationMs": duration_ms,
        "expect": args.expect,
        "expectMatched": expect_matched,
        "expectContext": context,
        "outputTail": output_tail(output),
        "git": git_evidence(project),
    }
    path = append_entry(project, args.bug, entry)
    print(json.dumps({"ok": True, "ledger": str(path), "entry": entry}, ensure_ascii=False))


def is_repro(entry: dict) -> bool:
    if entry.get("type") != "run":
        return False
    failed = bool(entry.get("timedOut")) or entry.get("exit") != 0
    if not failed:
        return False
    if entry.get("expect") is not None and entry.get("expect") != "":
        return entry.get("expectMatched") is True
    return True


def is_expect_anchored(entry: dict) -> bool:
    return entry.get("type") == "run" and bool(entry.get("expect"))


def is_verify(entry: dict, identity: dict) -> bool:
    return entry.get("type") == "run" and entry.get("exit") == 0 and not entry.get("timedOut") and entry.get("identity") == identity


def diff_identity(left: dict | None, right: dict | None) -> dict:
    if left is None or right is None:
        return {}
    keys = sorted(set(left) | set(right))
    return {key: {"repro": left.get(key), "pass": right.get(key)} for key in keys if left.get(key) != right.get(key)}


def analyze(entries: list[dict]) -> dict:
    first_failing = next(
        (entry for entry in entries if entry.get("type") == "run" and (entry.get("timedOut") or entry.get("exit") != 0)),
        None,
    )
    anchored_failures = [
        entry for entry in entries if entry.get("type") == "run" and (entry.get("timedOut") or entry.get("exit") != 0) and entry.get("expect")
    ]
    repros: list[tuple[int, dict]] = [(index, entry) for index, entry in enumerate(entries) if is_repro(entry)]
    for index, repro in repros:
        identity = repro.get("identity")
        for later in entries[index + 1 :]:
            if is_verify(later, identity):
                return {
                    "ok": True,
                    "verified": True,
                    "speculative": False,
                    "reproduced": True,
                    "reproIdentity": identity,
                    "verifyIdentity": later.get("identity"),
                    "failureKind": None,
                }

    speculative = next((entry for entry in reversed(entries) if entry.get("type") == "unreproduced"), None)
    if speculative:
        return {
            "ok": True,
            "verified": False,
            "speculative": True,
            "reproduced": bool(repros),
            "reason": speculative.get("reason"),
            "path": speculative.get("path"),
            "attemptCount": speculative.get("attemptCount"),
            "lastIdentity": speculative.get("lastIdentity"),
            "anyExpectMatched": speculative.get("anyExpectMatched"),
            "failureKind": None,
        }

    passing = [entry for entry in entries if entry.get("type") == "run" and entry.get("exit") == 0 and not entry.get("timedOut")]
    later_mismatch = None
    if repros:
        first_repro_index, first_repro = repros[0]
        later_mismatch = next(
            (entry for entry in entries[first_repro_index + 1 :] if entry.get("type") == "run" and entry.get("exit") == 0 and not entry.get("timedOut") and entry.get("identity") != first_repro.get("identity")),
            None,
        )

    if first_failing is None:
        failure = "no_repro"
    elif anchored_failures and not repros:
        failure = "expect_not_matched"
    elif later_mismatch is not None:
        failure = "identity_mismatch"
    else:
        failure = "no_verify"

    result = {
        "ok": False,
        "verified": False,
        "speculative": False,
        "reproduced": bool(repros),
        "reproIdentity": repros[0][1].get("identity") if repros else None,
        "failureKind": failure,
    }
    if failure == "identity_mismatch":
        base = repros[0][1] if repros else first_failing
        mismatch = later_mismatch or (passing[0] if passing else None)
        result["identityDiff"] = diff_identity(base.get("identity") if base else None, mismatch.get("identity") if mismatch else None)
    return result


def status(args: argparse.Namespace) -> None:
    project = resolve_project(args.project)
    entries = read_entries(ledger_path(project, args.bug))
    summary = analyze(entries)
    summary.update(
        {
            "bug": slugify(args.bug),
            "entries": len(entries),
            "expectMatched": any(entry.get("expectMatched") is True for entry in entries if entry.get("type") == "run"),
        }
    )
    print(json.dumps(summary, ensure_ascii=False))


def close(args: argparse.Namespace) -> None:
    project = resolve_project(args.project)
    entries = read_entries(ledger_path(project, args.bug))
    summary = analyze(entries)
    summary.update({"bug": slugify(args.bug), "entries": len(entries)})
    print(json.dumps(summary, ensure_ascii=False))
    if not summary.get("ok"):
        raise SystemExit(1)


def mark_unreproduced(args: argparse.Namespace) -> None:
    require_posix()
    project = resolve_project(args.project)
    if args.no_probe_possible and args.no_stable_expect:
        raise SystemExit("Choose only one impossibility flag")
    entries = read_entries(ledger_path(project, args.bug))
    anchored_attempts = [entry for entry in entries if is_expect_anchored(entry)]
    run_attempts = [entry for entry in entries if entry.get("type") == "run"]
    if args.no_probe_possible:
        path = "no-probe-possible"
    elif args.no_stable_expect:
        path = "no-stable-expect"
    elif anchored_attempts:
        path = "anchored-attempt"
    else:
        raise SystemExit(
            "mark-unreproduced requires a prior anchored run or "
            "--no-probe-possible/--no-stable-expect with --reason"
        )
    last_attempt = run_attempts[-1] if run_attempts else None
    entry = {
        "ts": utc_now(),
        "type": "unreproduced",
        "reason": args.reason,
        "path": path,
        "attemptCount": len(run_attempts),
        "lastIdentity": last_attempt.get("identity") if last_attempt else None,
        "anyExpectMatched": any(entry.get("expectMatched") is True for entry in run_attempts),
        "git": git_evidence(project),
    }
    path_obj = append_entry(project, args.bug, entry)
    print(json.dumps({"ok": True, "ledger": str(path_obj), "entry": entry}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record fail-fix-same-probe verification for behavioral bug fixes.")
    sub = parser.add_subparsers(dest="command_name", required=True)

    run_p = sub.add_parser("run", help="Execute and record a probe")
    run_p.add_argument("--project", required=True, type=Path)
    run_p.add_argument("--bug", required=True)
    run_p.add_argument("--cwd", default=".")
    run_p.add_argument("--expect")
    run_p.add_argument("--timeout", type=float, default=600)
    run_p.add_argument("--shell", action="store_true")
    run_p.add_argument("command", nargs=argparse.REMAINDER)
    run_p.set_defaults(func=run_probe)

    for name, func in (("status", status), ("close", close)):
        sub_p = sub.add_parser(name)
        sub_p.add_argument("--project", required=True, type=Path)
        sub_p.add_argument("--bug", required=True)
        sub_p.set_defaults(func=func)

    mark_p = sub.add_parser("mark-unreproduced")
    mark_p.add_argument("--project", required=True, type=Path)
    mark_p.add_argument("--bug", required=True)
    mark_p.add_argument("--reason", required=True)
    mark_p.add_argument("--no-probe-possible", action="store_true")
    mark_p.add_argument("--no-stable-expect", action="store_true")
    mark_p.set_defaults(func=mark_unreproduced)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if hasattr(args, "command") and args.command and args.command[0] == "--":
        args.command = args.command[1:]
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
