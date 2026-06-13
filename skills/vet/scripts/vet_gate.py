#!/usr/bin/env python3
"""Evidence gate for techne/vet diff reviews.

Python 3 stdlib only. POSIX developer environments only.

Claim normalization order, used for content-derived ids:
1. CRLF -> LF
2. Strip trailing whitespace per line
3. Trim leading/trailing blank lines
4. Preserve internal whitespace and line structure
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import tokenize
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "techne.vet/1"
MAX_LISTED_REFS = 200
IDENTITY_TRAILERS = {
    "signed-off-by",
    "co-authored-by",
    "reviewed-by",
    "acked-by",
    "tested-by",
    "reported-by",
    "suggested-by",
    "helped-by",
    "cc",
}

TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|__tests__|spec)(/|$)"
    r"|(^|/)[^/]*(?:_test|\.test|\.spec)\.[^/]+$"
    r"|(^|/)[^/]*Tests\.swift$"
)

LOCKFILE_NAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.lock",
    "poetry.lock",
    "Pipfile.lock",
    "Gemfile.lock",
    "composer.lock",
}

EXEMPT_PREFIXES = (
    "node_modules/",
    "vendor/",
    "vendors/",
    "dist/",
    "build/",
    "target/",
    "coverage/",
    ".next/",
    ".nuxt/",
    ".svelte-kit/",
    ".git/",
    ".techne/",
)

PY_EXTS = {".py"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
C_LIKE_EXTS = {
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".cxx",
    ".hpp",
    ".hh",
    ".java",
    ".kt",
    ".kts",
    ".go",
    ".rs",
    ".swift",
    ".m",
    ".mm",
    ".cs",
    ".fs",
    ".vb",
    ".php",
}
CODE_EXTS = PY_EXTS | JS_EXTS | C_LIKE_EXTS
BRACE_EXTS = JS_EXTS | C_LIKE_EXTS

PY_MASK_TOKEN_TYPES = {tokenize.STRING, tokenize.COMMENT}
for _token_name in (
    "FSTRING_START",
    "FSTRING_MIDDLE",
    "FSTRING_END",
    "TSTRING_START",
    "TSTRING_MIDDLE",
    "TSTRING_END",
):
    _token_type = getattr(tokenize, _token_name, None)
    if isinstance(_token_type, int):
        PY_MASK_TOKEN_TYPES.add(_token_type)

CONTROL_WORDS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "return",
    "throw",
    "else",
    "do",
    "try",
    "finally",
    "with",
    "using",
}


@dataclasses.dataclass
class Definition:
    name: str
    kind: str
    line: int
    indent: int
    text: str


@dataclasses.dataclass
class MaskResult:
    lines: list[str]
    confidence: str
    uncertain_lines: set[int]
    family: str
    notes: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_posix() -> None:
    if os.name != "posix":
        raise SystemExit("vet_gate.py v1 supports POSIX developer environments only (macOS/Linux).")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip(".-_")
    return slug or "review"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def json_load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing required artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))


def fail(kind: str, message: str, extra: dict[str, Any] | None = None) -> None:
    payload = {"ok": False, "failureKind": kind, "message": message}
    if extra:
        payload.update(extra)
    print_json(payload)
    raise SystemExit(1)


def run_git(project: Path, args: list[str], *, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=project,
        text=True,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise RuntimeError(message)
    return result


def git_stdout(project: Path, args: list[str]) -> str:
    return run_git(project, args).stdout


def resolve_project(value: Path) -> Path:
    project = value.resolve()
    if not project.is_dir():
        raise SystemExit(f"Project directory does not exist: {project}")
    return project


def require_git_repo(project: Path) -> None:
    result = run_git(project, ["rev-parse", "--is-inside-work-tree"], check=False)
    if result.returncode != 0 or result.stdout.strip() != "true":
        fail("not_git_repository", "init requires a git repository")


def rev_parse(project: Path, ref: str) -> str:
    result = run_git(project, ["rev-parse", "--verify", ref], check=False)
    if result.returncode != 0:
        fail("bad_ref", f"Cannot resolve git ref: {ref}", {"gitStderr": result.stderr.strip()})
    return result.stdout.strip()


def current_head(project: Path) -> str:
    return git_stdout(project, ["rev-parse", "HEAD"]).strip()


def merge_base(project: Path, base: str, head: str) -> str:
    result = run_git(project, ["merge-base", base, head], check=False)
    if result.returncode != 0 or not result.stdout.strip():
        fail(
            "no_merge_base",
            "No local merge base for base...head. Fetch the base ref and enough history "
            "(for example: git fetch --deepen 50 origin <base>) or re-checkout with full history.",
            {"gitStderr": result.stderr.strip()},
        )
    return result.stdout.strip()


def is_under(path: str, prefix: str) -> bool:
    clean = prefix.rstrip("/")
    return path == clean or path.startswith(clean + "/")


def dirty_entries(project: Path) -> list[str]:
    result = run_git(project, ["status", "--porcelain", "--untracked-files=all"], check=False)
    entries: list[str] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        path = line[3:] if len(line) > 3 else line
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if is_under(path, ".techne"):
            continue
        if path == ".gitignore" and gitignore_delta_is_only_techne(project):
            continue
        entries.append(line)
    return entries


def gitignore_delta_is_only_techne(project: Path) -> bool:
    gitignore = project / ".gitignore"
    if not gitignore.exists():
        return False
    result = run_git(project, ["ls-files", "--error-unmatch", ".gitignore"], check=False)
    if result.returncode != 0:
        content = [line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines() if line.strip()]
        return content == [".techne/"]
    diff = run_git(project, ["diff", "--", ".gitignore"], check=False).stdout
    meaningful: list[str] = []
    for raw in diff.splitlines():
        if raw.startswith(("diff --git", "index ", "--- ", "+++ ", "@@")):
            continue
        meaningful.append(raw)
    return bool(meaningful) and all(line in {"+.techne/", ""} for line in meaningful)


def ensure_gitignore(project: Path) -> None:
    gitignore = project / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    if ".techne/" not in [line.strip() for line in existing]:
        prefix = "" if not existing or existing[-1] == "" else "\n"
        with gitignore.open("a", encoding="utf-8") as handle:
            handle.write(f"{prefix}.techne/\n")


def review_dir(project: Path, review: str) -> Path:
    return project / ".techne" / "review" / slugify(review)


def git_show_text(project: Path, treeish: str, file_path: str) -> str | None:
    result = run_git(project, ["show", f"{treeish}:{file_path}"], check=False)
    if result.returncode != 0:
        return None
    return result.stdout


def tracked_file_lines(project: Path, treeish: str, file_path: str) -> list[str] | None:
    text = git_show_text(project, treeish, file_path)
    if text is None:
        return None
    return text.splitlines()


def file_exists_at(project: Path, treeish: str, file_path: str) -> bool:
    return run_git(project, ["cat-file", "-e", f"{treeish}:{file_path}"], check=False).returncode == 0


def normalize_claim_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def claim_id(source: str, text: str) -> str:
    return "c-" + sha256_text(source + "\0" + normalize_claim_text(text))[:12]


def split_claim_file(text: str) -> list[str]:
    normalized = normalize_claim_text(text)
    if not normalized:
        return []
    chunks = re.split(r"\n\s*\n", normalized)
    return [normalize_claim_text(chunk) for chunk in chunks if normalize_claim_text(chunk)]


def add_claim(claims: dict[str, dict[str, Any]], source: str, text: str, extra: dict[str, Any] | None = None) -> None:
    normalized = normalize_claim_text(text)
    if not normalized:
        return
    cid = claim_id(source, normalized)
    if cid in claims:
        claims[cid].setdefault("duplicates", 0)
        claims[cid]["duplicates"] += 1
        return
    item = {"id": cid, "source": source, "text": normalized}
    if extra:
        item.update(extra)
    claims[cid] = item


def parse_claim_arg(value: str) -> tuple[str, str]:
    if ":" not in value:
        raise SystemExit("--claim must use <source>:<text>")
    source, text = value.split(":", 1)
    source = source.strip()
    text = text.strip()
    if not source or not text:
        raise SystemExit("--claim requires non-empty source and text")
    return source, text


def parse_trailer_block(paragraphs: list[str]) -> tuple[list[str], list[str]]:
    if not paragraphs:
        return [], []
    last = paragraphs[-1]
    lines = [line for line in last.splitlines() if line.strip()]
    if not lines:
        return paragraphs, []
    if all(re.match(r"^[A-Za-z0-9-]+:\s+.+", line) for line in lines):
        return paragraphs[:-1], lines
    return paragraphs, []


def commit_claims(project: Path, merge_base_sha: str, head_sha: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    fmt = "%H%x1f%s%x1f%b%x1e"
    result = run_git(project, ["log", f"--format={fmt}", f"{merge_base_sha}..{head_sha}"], check=False)
    if result.returncode != 0:
        return [], [], []
    claim_map: dict[str, dict[str, Any]] = {}
    messages: list[dict[str, Any]] = []
    trailers: list[dict[str, Any]] = []
    for raw in result.stdout.split("\x1e"):
        raw = raw.strip("\n")
        if not raw:
            continue
        parts = raw.split("\x1f", 2)
        if len(parts) < 3:
            continue
        sha, subject, body = parts
        messages.append({"sha": sha, "subject": subject, "body": body})
        add_claim(claim_map, "commit-subject", subject, {"commit": sha})
        paragraphs = split_claim_file(body)
        body_paragraphs, trailer_lines = parse_trailer_block(paragraphs)
        for paragraph in body_paragraphs:
            add_claim(claim_map, "commit-body", paragraph, {"commit": sha})
        for line in trailer_lines:
            key = line.split(":", 1)[0].strip()
            trailer = {"commit": sha, "key": key, "text": line}
            if key.lower() in IDENTITY_TRAILERS:
                trailer["classification"] = "identity-trailer"
                trailers.append(trailer)
            else:
                trailer["classification"] = "claim"
                trailers.append(trailer)
                add_claim(claim_map, "commit-body", line, {"commit": sha, "trailerKey": key})
    return messages, trailers, list(claim_map.values())


def external_claims(args: argparse.Namespace) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    has_external = bool(args.claims_file) or bool(args.claim)
    if args.no_claims and has_external:
        raise SystemExit("Choose --no-claims or --claims-file/--claim, not both")
    if not args.no_claims and not has_external:
        raise SystemExit("init requires --claims-file/--claim or --no-claims")
    if args.no_claims:
        return "none", [], {"choice": "none", "digest": sha256_text("none")}
    claim_map: dict[str, dict[str, Any]] = {}
    files: list[dict[str, Any]] = []
    for claim_file in args.claims_file or []:
        path = Path(claim_file).resolve()
        text = path.read_text(encoding="utf-8")
        digest = sha256_text(text)
        files.append({"path": str(path), "sha256": digest})
        for paragraph in split_claim_file(text):
            add_claim(claim_map, f"claims-file:{path.name}", paragraph, {"fileSha256": digest})
    for value in args.claim or []:
        source, text = parse_claim_arg(value)
        add_claim(claim_map, source, text, {"inline": True})
    payload = {"choice": "provided", "files": files, "claims": sorted(claim_map.values(), key=lambda item: item["id"])}
    return "provided", list(claim_map.values()), {"choice": "provided", "digest": sha256_text(json.dumps(payload, sort_keys=True)), "files": files}


def mask_python(text: str) -> MaskResult:
    lines = text.splitlines()
    chars = [list(line) for line in lines]
    uncertain: set[int] = set()
    notes: list[str] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for tok in tokens:
            if tok.type not in PY_MASK_TOKEN_TYPES:
                continue
            (start_line, start_col), (end_line, end_col) = tok.start, tok.end
            for line_no in range(start_line, end_line + 1):
                if line_no < 1 or line_no > len(chars):
                    continue
                line = chars[line_no - 1]
                start = start_col if line_no == start_line else 0
                end = end_col if line_no == end_line else len(line)
                for index in range(start, min(end, len(line))):
                    line[index] = " "
    except tokenize.TokenError as exc:
        uncertain.update(range(1, len(lines) + 1))
        notes.append(f"python_tokenize_error:{exc.args[0] if exc.args else 'unknown'}")
    return MaskResult(["".join(line) for line in chars], "weak" if uncertain else "confident", uncertain, "python", notes)


def mask_light(text: str, ext: str) -> MaskResult:
    lines = text.splitlines()
    chars = [list(line) for line in lines]
    uncertain: set[int] = set()
    notes: list[str] = []
    in_block = False
    block_start = 0
    in_string: str | None = None
    string_start = 0
    in_template = False
    template_start = 0

    def blank(line_no: int, start: int, end: int) -> None:
        if line_no < 1 or line_no > len(chars):
            return
        line = chars[line_no - 1]
        for idx in range(start, min(end, len(line))):
            line[idx] = " "

    for line_no, line in enumerate(lines, start=1):
        i = 0
        while i < len(line):
            ch = line[i]
            nxt = line[i + 1] if i + 1 < len(line) else ""
            if in_block:
                end = line.find("*/", i)
                if end < 0:
                    blank(line_no, i, len(line))
                    i = len(line)
                else:
                    blank(line_no, i, end + 2)
                    in_block = False
                    i = end + 2
                continue
            if in_template:
                if ch == "\\":
                    blank(line_no, i, min(i + 2, len(line)))
                    i += 2
                    continue
                if ch == "$" and nxt == "{":
                    uncertain.add(line_no)
                    notes.append("template_interpolation")
                blank(line_no, i, i + 1)
                if ch == "`":
                    in_template = False
                i += 1
                continue
            if in_string:
                if ch == "\\":
                    blank(line_no, i, min(i + 2, len(line)))
                    i += 2
                    continue
                blank(line_no, i, i + 1)
                if ch == in_string:
                    in_string = None
                i += 1
                continue
            if ch == "/" and nxt == "/":
                blank(line_no, i, len(line))
                break
            if ch == "/" and nxt == "*":
                blank(line_no, i, i + 2)
                in_block = True
                block_start = line_no
                i += 2
                continue
            if ch in ("'", '"'):
                in_string = ch
                string_start = line_no
                blank(line_no, i, i + 1)
                i += 1
                continue
            if ext in JS_EXTS and ch == "`":
                in_template = True
                template_start = line_no
                blank(line_no, i, i + 1)
                i += 1
                continue
            if ch == "/" and ext in JS_EXTS:
                uncertain.add(line_no)
                notes.append("regex_literal_ambiguity")
            if line[i : i + 2] == 'R"' or line[i : i + 2] in {"r#", "R#"}:
                uncertain.add(line_no)
                notes.append("raw_string")
            if line[i : i + 3] == '"""':
                uncertain.add(line_no)
                notes.append("text_block_or_multiline_string")
            i += 1
    if in_block:
        uncertain.update(range(block_start, len(lines) + 1))
        notes.append("unterminated_block_comment")
    if in_string:
        uncertain.update(range(string_start, len(lines) + 1))
        notes.append("unterminated_string")
    if in_template:
        uncertain.update(range(template_start, len(lines) + 1))
        notes.append("unterminated_template")
    return MaskResult(["".join(line) for line in chars], "weak" if uncertain else "confident", uncertain, "brace", notes)


def lexical_mask(path: str, text: str) -> MaskResult:
    ext = Path(path).suffix
    if ext in PY_EXTS:
        return mask_python(text)
    if ext in JS_EXTS or ext in C_LIKE_EXTS:
        return mask_light(text, ext)
    return MaskResult(text.splitlines(), "weak", set(range(1, len(text.splitlines()) + 1)), "unknown", ["unknown_extension"])


def leading_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def detect_definitions(line: str, line_no: int) -> list[Definition]:
    stripped = line.strip()
    if not stripped:
        return []
    indent = leading_indent(line)
    defs: list[Definition] = []
    patterns = [
        (r"^(?:export\s+default\s+|export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", "function"),
        (r"^(?:export\s+)?(?:class|interface|struct|enum|protocol|trait)\s+([A-Za-z_$][\w$]*)\b", "type"),
        (r"^(?:public\s+|private\s+|internal\s+|open\s+|static\s+|async\s+|mutating\s+|override\s+)*func\s+([A-Za-z_]\w*)\s*\(", "function"),
        (r"^(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)\s*\(", "function"),
        (r"^def\s+([A-Za-z_]\w*)\s*\(", "function"),
        (r"^class\s+([A-Za-z_]\w*)\b", "class"),
        (r"^(?:export\s+)?(?:const|let|var|type)\s+([A-Za-z_$][\w$]*)\b", "binding"),
        (r"^impl\s+([A-Za-z_]\w*)\b", "impl"),
    ]
    for pattern, kind in patterns:
        match = re.match(pattern, stripped)
        if match:
            defs.append(Definition(match.group(1), kind, line_no, indent, stripped))
            return defs
    method = re.match(r"^(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^;{}]*\)\s*(?:\{|$)", stripped)
    if method and method.group(1) not in CONTROL_WORDS:
        defs.append(Definition(method.group(1), "method", line_no, indent, stripped))
    c_func = re.match(
        r"^(?!(?:if|for|while|switch|return|catch)\b)[A-Za-z_][\w:<>\*&\s\[\]]+\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*(?:\{|$)",
        stripped,
    )
    if c_func and c_func.group(1) not in CONTROL_WORDS:
        defs.append(Definition(c_func.group(1), "function", line_no, indent, stripped))
    return defs


def all_definitions(masked_lines: list[str], uncertain: set[int]) -> list[Definition]:
    defs: list[Definition] = []
    for index, line in enumerate(masked_lines, start=1):
        if index in uncertain:
            continue
        defs.extend(detect_definitions(line, index))
    return defs


def python_unit_stack(defs: list[Definition], changed_line: int, changed_indent: int) -> list[Definition]:
    stack: list[Definition] = []
    last_indent = 10**9
    for definition in sorted((item for item in defs if item.line <= changed_line), key=lambda item: item.line, reverse=True):
        if definition.indent < changed_indent and definition.indent < last_indent:
            stack.append(definition)
            last_indent = definition.indent
    return list(reversed(stack))


def line_indent(masked_lines: list[str], line_no: int) -> int:
    if line_no < 1 or line_no > len(masked_lines):
        return 0
    return leading_indent(masked_lines[line_no - 1])


def has_open_after_def(line: str, definition: Definition) -> bool:
    pos = line.find(definition.name)
    segment = line[pos:] if pos >= 0 else line
    semi = segment.find(";")
    brace = segment.find("{")
    return brace >= 0 and (semi < 0 or brace < semi)


def is_never_opening_declaration(line: str) -> bool:
    stripped = line.strip()
    if not stripped.endswith(";"):
        return False
    brace = stripped.find("{")
    semi = stripped.find(";")
    return brace < 0 or semi < brace


def brace_unit_stack(masked_lines: list[str], changed_line: int, uncertain: set[int]) -> tuple[list[Definition], bool, list[str]]:
    depth = 0
    active: list[tuple[Definition, int]] = []
    pending: list[Definition] = []
    notes: list[str] = []
    stack_at_changed: list[Definition] = []
    confident = True
    for line_no, line in enumerate(masked_lines, start=1):
        if line_no in uncertain:
            confident = False
            if line_no <= changed_line:
                notes.append(f"uncertain_line:{line_no}")
        active = [(definition, block_depth) for definition, block_depth in active if depth >= block_depth]
        stripped = line.strip()
        if stripped.startswith("{") and pending:
            for definition in pending:
                active.append((definition, depth + 1))
            pending = []
        elif stripped and pending:
            notes.append(f"pending_definition_cleared:{line_no}")
            pending = []
        defs = [] if line_no in uncertain else detect_definitions(line, line_no)
        for definition in defs:
            if has_open_after_def(line, definition):
                active.append((definition, depth + 1))
            elif is_never_opening_declaration(line):
                notes.append(f"prototype_ignored:{line_no}:{definition.name}")
            else:
                pending.append(definition)
        if line_no == changed_line:
            stack_at_changed = [definition for definition, _ in active]
            break
        for ch in line:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth = max(0, depth - 1)
                active = [(definition, block_depth) for definition, block_depth in active if depth >= block_depth]
    return stack_at_changed, confident, notes


def symbol_key(symbol: dict[str, Any]) -> str:
    return "|".join(
        [
            symbol.get("name") or symbol.get("symbol") or "",
            symbol.get("definingFile") or "",
            str(symbol.get("definingLine") or ""),
        ]
    )


def add_candidate_symbol(candidates: dict[str, dict[str, Any]], symbol: dict[str, Any]) -> dict[str, Any]:
    key = symbol_key(symbol)
    if key not in candidates:
        symbol["sources"] = [symbol.get("source")] if symbol.get("source") else []
        symbol["hunkIds"] = [symbol.get("hunkId")] if symbol.get("hunkId") else []
        candidates[key] = symbol
        return symbol
    existing = candidates[key]
    source = symbol.get("source")
    if source and source not in existing.setdefault("sources", []):
        existing["sources"].append(source)
    hunk_id = symbol.get("hunkId")
    if hunk_id and hunk_id not in existing.setdefault("hunkIds", []):
        existing["hunkIds"].append(hunk_id)
    return existing


def make_symbol(definition: Definition, file_path: str, source: str, hunk_id: str, relation: str) -> dict[str, Any]:
    seed = f"{file_path}:{definition.line}:{definition.name}:{source}"
    return {
        "id": "s-" + sha256_text(seed)[:12],
        "name": definition.name,
        "symbol": definition.name,
        "kind": definition.kind,
        "source": source,
        "definingFile": file_path,
        "definingLine": definition.line,
        "hunkId": hunk_id,
        "stackRelation": relation,
        "lineText": definition.text,
    }


def parse_git_diff_paths(raw: str) -> tuple[str | None, str | None]:
    match = re.match(r"^diff --git a/(.+) b/(.+)$", raw)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def parse_diff_hunks(
    diff_text: str,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[int]], dict[str, list[str]], dict[str, list[int]], dict[str, bool]]:
    hunks: dict[str, list[dict[str, Any]]] = {}
    changed_lines: dict[str, list[int]] = {}
    added_text: dict[str, list[str]] = {}
    removed_lines: dict[str, list[int]] = {}
    binary: dict[str, bool] = {}
    current: str | None = None
    old_path: str | None = None
    new_path: str | None = None
    hunk: dict[str, Any] | None = None
    old_line = 0
    new_line = 0
    hunk_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@ ?(.*)$")
    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            old_path, new_path = parse_git_diff_paths(raw)
            current = None
            hunk = None
        elif raw.startswith("--- "):
            if raw.startswith("--- a/"):
                old_path = raw[6:]
            elif raw == "--- /dev/null":
                old_path = None
        elif raw.startswith("+++ b/"):
            new_path = raw[6:]
            current = new_path
            hunks.setdefault(current, [])
            changed_lines.setdefault(current, [])
            added_text.setdefault(current, [])
        elif raw == "+++ /dev/null":
            new_path = None
            current = old_path
            if current:
                hunks.setdefault(current, [])
                changed_lines.setdefault(current, [])
                added_text.setdefault(current, [])
        elif raw.startswith("Binary files "):
            parts = raw.split(" and ")
            if parts and parts[0].startswith("Binary files a/"):
                binary[parts[0][15:]] = True
            if len(parts) > 1 and parts[1].startswith("b/"):
                binary[parts[1][2:].split(" differ")[0]] = True
        elif current and raw.startswith("@@ "):
            match = hunk_re.match(raw)
            if not match:
                continue
            old_start = int(match.group(1))
            old_count = int(match.group(2) or "1")
            new_start = int(match.group(3))
            new_count = int(match.group(4) or "1")
            hunk_id = f"h{sum(len(items) for items in hunks.values()) + 1}"
            hunk = {
                "id": hunk_id,
                "file": current,
                "oldFile": old_path,
                "newFile": new_path,
                "oldStart": old_start,
                "oldCount": old_count,
                "oldLines": list(range(old_start, old_start + old_count)) if old_count else [],
                "newStart": new_start,
                "newCount": new_count,
                "newLines": list(range(new_start, new_start + new_count)) if new_count else [],
                "headerHint": match.group(5).strip(),
            }
            hunks[current].append(hunk)
            old_line = old_start
            new_line = new_start
        elif current and hunk is not None:
            if raw.startswith("+") and not raw.startswith("+++"):
                changed_lines[current].append(new_line)
                added_text[current].append(raw[1:])
                new_line += 1
            elif raw.startswith("-") and not raw.startswith("---"):
                if old_path:
                    removed_lines.setdefault(old_path, []).append(old_line)
                old_line += 1
            elif raw.startswith(" "):
                old_line += 1
                new_line += 1
    return hunks, changed_lines, added_text, removed_lines, binary


def classify_file(path: str, is_binary: bool) -> str:
    name = Path(path).name
    if is_binary:
        return "binary"
    if name in LOCKFILE_NAMES:
        return "candidateExempt"
    if any(is_under(path, prefix.rstrip("/")) for prefix in EXEMPT_PREFIXES):
        return "candidateExempt"
    return "reviewableText"


def is_test_path(path: str) -> bool:
    return bool(TEST_PATH_RE.search(path))


def changed_files(project: Path, merge_base_sha: str, head_sha: str) -> list[dict[str, Any]]:
    result = run_git(project, ["diff", "--name-status", "--find-renames", merge_base_sha, head_sha], check=False)
    files: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        path = parts[-1]
        record = {"path": path, "status": status}
        if status.startswith(("R", "C")) and len(parts) >= 3:
            record["oldPath"] = parts[1]
            record["newPath"] = parts[2]
        elif status == "D":
            record["oldPath"] = path
            record["newPath"] = None
        elif status == "A":
            record["oldPath"] = None
            record["newPath"] = path
        else:
            record["oldPath"] = path
            record["newPath"] = path
        files.append(record)
    return files


def compute_scope(project: Path, review: str, base_ref: str, head_ref: str, allow_dirty: bool, claims_info: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
    require_git_repo(project)
    base_sha = rev_parse(project, base_ref)
    head_sha = rev_parse(project, head_ref)
    current = current_head(project)
    if current != head_sha:
        fail("head_mismatch", "Current HEAD must equal the resolved --head before init", {"currentHead": current, "headSha": head_sha})
    dirty = dirty_entries(project)
    if dirty and not allow_dirty:
        fail("dirty_worktree", "Worktree has changes outside .techne/. Pass --allow-dirty to record the escape.", {"dirty": dirty})
    merge_base_sha = merge_base(project, base_sha, head_sha)
    diff_text = git_stdout(project, ["diff", "--unified=0", "--find-renames", "--no-ext-diff", "--no-color", merge_base_sha, head_sha])
    hunks_by_file, changed_head_lines, added_lines, removed_base_lines, binary_map = parse_diff_hunks(diff_text)
    files = changed_files(project, merge_base_sha, head_sha)
    commit_messages, commit_trailers, commit_claim_items = commit_claims(project, merge_base_sha, head_sha)
    claim_map = {item["id"]: item for item in claims}
    for item in commit_claim_items:
        claim_map.setdefault(item["id"], item)

    candidate_symbols: dict[str, dict[str, Any]] = {}
    all_hunks: list[dict[str, Any]] = []
    changed_file_records: list[dict[str, Any]] = []
    prod_changed = False
    tests_changed = False
    mask_contract: dict[str, Any] = {
        "python": sorted(PY_EXTS),
        "jsTs": sorted(JS_EXTS),
        "cLike": sorted(C_LIKE_EXTS),
        "unknownExtensions": "weak",
    }

    for item in files:
        path = item["path"]
        old_path = item.get("oldPath") or path
        classification = classify_file(path, binary_map.get(path, False))
        if classification == "reviewableText":
            if is_test_path(path):
                tests_changed = True
            else:
                prod_changed = True
        text = git_show_text(project, head_sha, path) if classification == "reviewableText" else None
        mask = lexical_mask(path, text or "") if text is not None else None
        defs = all_definitions(mask.lines, mask.uncertain_lines) if mask else []
        base_text = git_show_text(project, merge_base_sha, old_path) if classification == "reviewableText" and old_path else None
        base_mask = lexical_mask(old_path, base_text or "") if base_text is not None else None
        base_defs = all_definitions(base_mask.lines, base_mask.uncertain_lines) if base_mask else []
        file_hunks = hunks_by_file.get(path, [])
        for hunk in file_hunks:
            hunk = dict(hunk)
            hunk["classification"] = classification
            hunk["unitCandidates"] = []
            hunk["unitBinding"] = "none"
            hunk["requiresDisposition"] = False
            hunk["maskConfidence"] = mask.confidence if mask else "not-scanned"
            hunk["maskNotes"] = mask.notes if mask else []
            first_line = hunk["newLines"][0] if hunk["newLines"] else hunk["newStart"]
            affected = set(hunk["newLines"] or [first_line])
            removed_affected = set(hunk.get("oldLines") or [])
            removed_candidate = False
            if classification == "reviewableText" and base_mask:
                for definition in base_defs:
                    if definition.line in removed_affected and definition.line not in base_mask.uncertain_lines:
                        symbol = make_symbol(definition, hunk.get("oldFile") or old_path, "removed-definition", hunk["id"], "removed-line")
                        symbol["tree"] = "base"
                        stored = add_candidate_symbol(candidate_symbols, symbol)
                        if stored["id"] not in hunk["unitCandidates"]:
                            hunk["unitCandidates"].append(stored["id"])
                        removed_candidate = True
            if classification == "reviewableText" and mask:
                if mask.confidence != "confident" and (mask.family == "unknown" or affected & mask.uncertain_lines):
                    hunk["unitBinding"] = "weak"
                    hunk["requiresDisposition"] = True
                elif Path(path).suffix in PY_EXTS:
                    stack = python_unit_stack(defs, first_line, line_indent(mask.lines, first_line))
                    for index, definition in enumerate(stack):
                        relation = "outer" if index < len(stack) - 1 else "nearest"
                        symbol = make_symbol(definition, path, "enclosing-unit", hunk["id"], relation)
                        stored = add_candidate_symbol(candidate_symbols, symbol)
                        hunk["unitCandidates"].append(stored["id"])
                    hunk["unitBinding"] = "strong" if stack else "none"
                    hunk["requiresDisposition"] = not bool(stack)
                elif Path(path).suffix in BRACE_EXTS:
                    stack, brace_confident, notes = brace_unit_stack(mask.lines, first_line, mask.uncertain_lines)
                    hunk["braceNotes"] = notes
                    if not brace_confident:
                        hunk["unitBinding"] = "weak"
                        hunk["requiresDisposition"] = True
                    else:
                        for index, definition in enumerate(stack):
                            relation = "outer" if index < len(stack) - 1 else "nearest"
                            symbol = make_symbol(definition, path, "enclosing-unit", hunk["id"], relation)
                            stored = add_candidate_symbol(candidate_symbols, symbol)
                            hunk["unitCandidates"].append(stored["id"])
                        hunk["unitBinding"] = "strong" if stack else "none"
                        hunk["requiresDisposition"] = not bool(stack)
                else:
                    hunk["unitBinding"] = "weak"
                    hunk["requiresDisposition"] = True
                for definition in defs:
                    if definition.line in affected:
                        symbol = make_symbol(definition, path, "changed-definition", hunk["id"], "changed-line")
                        stored = add_candidate_symbol(candidate_symbols, symbol)
                        if stored["id"] not in hunk["unitCandidates"]:
                            hunk["unitCandidates"].append(stored["id"])
                        hunk["unitBinding"] = "strong"
                        hunk["requiresDisposition"] = False
                if removed_candidate and hunk["unitBinding"] == "none":
                    hunk["unitBinding"] = "removed"
                    hunk["requiresDisposition"] = False
            elif classification == "reviewableText" and removed_candidate:
                hunk["unitBinding"] = "removed"
                hunk["requiresDisposition"] = False
            elif classification == "reviewableText":
                hunk["unitBinding"] = "weak"
                hunk["requiresDisposition"] = True
            all_hunks.append(hunk)
        changed_file_records.append(
            {
                **item,
                "classification": classification,
                "testPath": is_test_path(path),
                "hunks": [hunk["id"] for hunk in file_hunks],
                "maskConfidence": mask.confidence if mask else "not-scanned",
                "maskFamily": mask.family if mask else None,
                "maskNotes": mask.notes if mask else [],
            }
        )

    return {
        "schema": SCHEMA,
        "review": slugify(review),
        "createdAt": utc_now(),
        "project": str(project),
        "baseRef": base_ref,
        "headRef": head_ref,
        "baseSha": base_sha,
        "headSha": head_sha,
        "mergeBaseSha": merge_base_sha,
        "allowDirty": allow_dirty,
        "dirty": dirty,
        "claimsDeclared": claims_info["choice"],
        "claimsDigest": claims_info["digest"],
        "claimsFiles": claims_info.get("files", []),
        "claims": sorted(claim_map.values(), key=lambda item: item["id"]),
        "commitMessages": commit_messages,
        "commitTrailers": commit_trailers,
        "changedFiles": changed_file_records,
        "hunks": all_hunks,
        "candidateSymbols": sorted(candidate_symbols.values(), key=lambda item: (item.get("definingFile") or "", item.get("definingLine") or 0, item["name"])),
        "changedHeadLines": {path: sorted(set(lines)) for path, lines in changed_head_lines.items()},
        "addedLines": added_lines,
        "removedBaseLines": {path: sorted(set(lines)) for path, lines in removed_base_lines.items()},
        "testsDelta": {"prodChanged": prod_changed, "testsChanged": tests_changed},
        "heuristics": {
            "testPathPattern": TEST_PATH_RE.pattern,
            "lockfiles": sorted(LOCKFILE_NAMES),
            "exemptPrefixes": list(EXEMPT_PREFIXES),
            "maskContract": mask_contract,
            "identityTrailerAllowlist": sorted(IDENTITY_TRAILERS),
        },
    }


def init(args: argparse.Namespace) -> None:
    project = resolve_project(args.project)
    claims_declared, external_items, claims_info = external_claims(args)
    claims_info["choice"] = claims_declared
    scope = compute_scope(project, args.review, args.base, args.head, args.allow_dirty, claims_info, external_items)
    out_dir = review_dir(project, args.review)
    existing_path = out_dir / "scope.json"
    if existing_path.exists():
        existing = json_load(existing_path)
        if existing.get("baseSha") != scope.get("baseSha") or existing.get("headSha") != scope.get("headSha"):
            fail("scope_changed", "Existing review slug is anchored to different SHAs; use a new slug.")
        if existing.get("claimsDigest") != scope.get("claimsDigest") or existing.get("claimsDeclared") != scope.get("claimsDeclared"):
            fail("claims_changed", "Existing review slug has a different claims choice/digest; use a new slug.")
    ensure_gitignore(project)
    json_dump(existing_path, scope)
    print_json({"ok": True, "scope": str(existing_path), "headSha": scope["headSha"], "candidateSymbols": len(scope["candidateSymbols"]), "hunks": len(scope["hunks"])})


def load_scope(project: Path, review: str) -> tuple[Path, dict[str, Any]]:
    out_dir = review_dir(project, review)
    return out_dir, json_load(out_dir / "scope.json")


def head_matches(project: Path, scope: dict[str, Any]) -> tuple[bool, str | None]:
    try:
        current = current_head(project)
    except Exception:
        return False, None
    return current == scope.get("headSha"), current


def hunk_ranges(scope: dict[str, Any], file_path: str) -> list[range]:
    ranges: list[range] = []
    for hunk in scope.get("hunks", []):
        if hunk.get("file") != file_path:
            continue
        lines = hunk.get("newLines") or []
        if lines:
            ranges.append(range(min(lines), max(lines) + 1))
    return ranges


def line_in_diff(scope: dict[str, Any], file_path: str, line: int) -> bool:
    return any(line in item for item in hunk_ranges(scope, file_path))


def verify_citation(project: Path, scope: dict[str, Any], citation: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    file_path = citation.get("file")
    if not file_path:
        return None, {"kind": "citation_missing_file", "citation": citation}
    lines = tracked_file_lines(project, scope["headSha"], file_path)
    if lines is None:
        return None, {"kind": "citation_file_missing", "file": file_path}
    start = citation.get("lineStart", citation.get("line"))
    end = citation.get("lineEnd", citation.get("line", start))
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start or end > len(lines):
        return None, {"kind": "citation_line_invalid", "file": file_path, "lineStart": start, "lineEnd": end, "lineCount": len(lines)}
    tag = "inDiff" if any(line_in_diff(scope, file_path, line) for line in range(start, end + 1)) else "context"
    return {"file": file_path, "lineStart": start, "lineEnd": end, "tag": tag}, None


def token_at_line(project: Path, head_sha: str, file_path: str, line_no: int, token: str) -> bool:
    lines = tracked_file_lines(project, head_sha, file_path)
    if lines is None or line_no < 1 or line_no > len(lines):
        return False
    return re.search(rf"(?<!\w){re.escape(token)}(?!\w)", lines[line_no - 1]) is not None


def file_line_text(project: Path, head_sha: str, file_path: str, line_no: int) -> str:
    lines = tracked_file_lines(project, head_sha, file_path)
    if lines is None or line_no < 1 or line_no > len(lines):
        return ""
    return lines[line_no - 1]


def review_symbols_by_name(review: dict[str, Any]) -> list[dict[str, Any]]:
    return list(review.get("symbols", []))


def symbol_name(item: dict[str, Any]) -> str:
    return item.get("symbol") or item.get("name") or ""


def candidate_matched(candidate: dict[str, Any], disposition: dict[str, Any]) -> bool:
    if disposition.get("id") and disposition.get("id") == candidate.get("id"):
        return True
    if symbol_name(disposition) != candidate.get("name"):
        return False
    if disposition.get("definingFile") and disposition.get("definingFile") != candidate.get("definingFile"):
        return False
    if disposition.get("definingLine") and disposition.get("definingLine") != candidate.get("definingLine"):
        return False
    return True


def changed_line_contains(scope: dict[str, Any], symbol: str) -> bool:
    for line_list in scope.get("addedLines", {}).values():
        for line in line_list:
            if re.search(rf"(?<!\w){re.escape(symbol)}(?!\w)", line):
                return True
    return False


def definition_floor_for_file(project: Path, scope: dict[str, Any], file_path: str) -> tuple[list[Definition], MaskResult | None]:
    text = git_show_text(project, scope["headSha"], file_path)
    if text is None:
        return [], None
    mask = lexical_mask(file_path, text)
    return all_definitions(mask.lines, mask.uncertain_lines), mask


def verify_enclosing_unit(project: Path, scope: dict[str, Any], hunk: dict[str, Any], disposition: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    symbol = disposition.get("symbol") or disposition.get("name")
    file_path = disposition.get("definingFile") or hunk.get("file")
    defining_line = disposition.get("definingLine")
    if not symbol or not isinstance(defining_line, int):
        return None, {"kind": "hunk_enclosing_unit_invalid", "hunkId": hunk.get("id")}
    if file_path != hunk.get("file"):
        return None, {"kind": "hunk_enclosing_unit_wrong_file", "hunkId": hunk.get("id")}
    first_line = (hunk.get("newLines") or [hunk.get("newStart")])[0]
    if defining_line > first_line:
        return None, {"kind": "hunk_enclosing_unit_after_hunk", "hunkId": hunk.get("id")}
    if not token_at_line(project, scope["headSha"], file_path, defining_line, symbol):
        return None, {"kind": "hunk_enclosing_unit_token_missing", "hunkId": hunk.get("id")}
    if hunk.get("unitBinding") != "weak":
        defs, _ = definition_floor_for_file(project, scope, file_path)
        nearer = [
            definition
            for definition in defs
            if defining_line < definition.line <= first_line and definition.name != symbol
        ]
        if nearer:
            return None, {
                "kind": "hunk_enclosing_unit_nearer_definition",
                "hunkId": hunk.get("id"),
                "nearest": dataclasses.asdict(nearer[-1]),
            }
    return {
        "id": "s-" + sha256_text(f"{file_path}:{defining_line}:{symbol}:declared-enclosing")[:12],
        "name": symbol,
        "symbol": symbol,
        "kind": "declared-enclosing",
        "source": "declared-enclosing-unit",
        "definingFile": file_path,
        "definingLine": defining_line,
        "hunkId": hunk.get("id"),
    }, None


def normalize_prefix(prefix: str) -> str:
    return prefix.strip("/ ")


def path_excluded(path: str, exclusions: list[dict[str, Any]]) -> dict[str, Any] | None:
    for exclusion in exclusions:
        prefix = normalize_prefix(str(exclusion.get("prefix", "")))
        if prefix and is_under(path, prefix):
            return exclusion
    return None


def grep_refs(project: Path, head_sha: str, token: str, paths: list[str] | None = None, fixed_word: bool = True) -> list[dict[str, Any]]:
    cmd = ["grep", "-n", "-F"]
    if fixed_word:
        cmd.append("-w")
    cmd.extend(["-e", token, head_sha])
    if paths:
        cmd.append("--")
        cmd.extend(paths)
    result = run_git(project, cmd, check=False)
    if result.returncode not in (0, 1):
        return []
    refs: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = line.split(":", 3)
        if len(parts) >= 4 and not parts[1].isdigit() and parts[2].isdigit():
            _, file_path, line_no, text = parts
        else:
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            file_path, line_no, text = parts
        if not line_no.isdigit():
            continue
        refs.append({"file": file_path, "line": int(line_no), "text": text})
    return refs


def subtract_own_ranges(refs: list[dict[str, Any]], scope: dict[str, Any], symbol: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    defining_file = symbol.get("definingFile")
    defining_line = symbol.get("definingLine")
    subtract_definition_line = symbol.get("source") != "removed-definition" and symbol.get("tree") != "base"
    for ref in refs:
        if line_in_diff(scope, ref["file"], ref["line"]):
            continue
        if subtract_definition_line and defining_file == ref["file"] and defining_line == ref["line"]:
            continue
        result.append(ref)
    return result


def raw_ref_buckets(refs: list[dict[str, Any]]) -> dict[str, int]:
    buckets: dict[str, int] = {}
    for ref in refs:
        top = ref["file"].split("/", 1)[0]
        buckets[top] = buckets.get(top, 0) + 1
    return dict(sorted(buckets.items()))


def bounded_pattern_valid(pattern: str, name: str, call_shapes: list[str]) -> bool:
    if name and name in pattern:
        return True
    for shape in call_shapes:
        if name in shape and shape in pattern:
            return True
    return False


def run_bounded_plan(project: Path, scope: dict[str, Any], name: str, plan: list[dict[str, Any]], call_shapes: list[str], failures: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    bounded_refs: list[dict[str, Any]] = []
    plan_report: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for index, item in enumerate(plan):
        pattern = item.get("pattern")
        if not pattern:
            failures.append({"kind": "bounded_plan_missing_pattern", "symbol": name, "index": index})
            continue
        if not item.get("rationale"):
            failures.append({"kind": "bounded_plan_missing_rationale", "symbol": name, "index": index})
        if not bounded_pattern_valid(pattern, name, call_shapes):
            failures.append({"kind": "bounded_pattern_missing_symbol", "symbol": name, "pattern": pattern})
        paths = item.get("paths") or None
        if isinstance(paths, str):
            paths = [paths]
        refs = grep_refs(project, scope["headSha"], pattern, paths=paths, fixed_word=False)
        for ref in refs:
            key = (ref["file"], ref["line"])
            if key not in seen:
                bounded_refs.append(ref)
                seen.add(key)
        plan_report.append({"pattern": pattern, "paths": paths or [], "rationale": item.get("rationale"), "refsFound": len(refs)})
    return bounded_refs, plan_report


def ref_key(ref: dict[str, Any]) -> tuple[str, int]:
    return (ref["file"], int(ref["line"]))


def collect_claim_dispositions(review: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    dispositions: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    for entry in review.get("claims", []):
        ids = entry.get("ids")
        if ids is None:
            ids = [entry.get("id")]
        if isinstance(ids, str):
            ids = [ids]
        for cid in ids or []:
            if not cid:
                failures.append({"kind": "claim_disposition_missing_id", "entry": entry})
                continue
            if cid in dispositions:
                failures.append({"kind": "claim_disposition_duplicate", "id": cid})
            dispositions[cid] = entry
    return dispositions, failures


def read_jsonl_line(path: Path, index: int) -> tuple[str | None, dict[str, Any] | None]:
    if not path.exists():
        return None, None
    with path.open("r", encoding="utf-8") as handle:
        for current, line in enumerate(handle):
            raw = line.rstrip("\n")
            if current == index:
                try:
                    return raw, json.loads(raw)
                except json.JSONDecodeError:
                    return raw, None
    return None, None


def validate_probe(project: Path, scope: dict[str, Any], probe: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    ledger = probe.get("ledger")
    index = probe.get("entryIndex")
    expected_hash = probe.get("entrySha256")
    if not ledger or not isinstance(index, int) or not expected_hash:
        return None, {"kind": "probe_invalid_reference"}
    ledger_path = Path(ledger)
    if not ledger_path.is_absolute():
        ledger_path = project / ledger_path
    try:
        ledger_path.resolve().relative_to(project.resolve())
    except ValueError:
        return None, {"kind": "probe_ledger_outside_project", "ledger": str(ledger_path)}
    raw, entry = read_jsonl_line(ledger_path, index)
    if raw is None or entry is None:
        return None, {"kind": "probe_missing", "ledger": str(ledger_path), "entryIndex": index}
    actual_hash = sha256_text(raw)
    if actual_hash != expected_hash:
        return None, {"kind": "probe_tampered", "ledger": str(ledger_path), "entryIndex": index, "actualSha256": actual_hash}
    if entry.get("type") != "run":
        return None, {"kind": "probe_not_run", "ledger": str(ledger_path), "entryIndex": index}
    failed = bool(entry.get("timedOut")) or entry.get("exit") != 0
    if not failed:
        return None, {"kind": "probe_passing", "ledger": str(ledger_path), "entryIndex": index}
    if entry.get("expect") not in (None, "") and entry.get("expectMatched") is not True:
        return None, {"kind": "probe_expect_not_matched", "ledger": str(ledger_path), "entryIndex": index}
    git = entry.get("git") or {}
    if git.get("head") != scope.get("headSha"):
        return None, {"kind": "probe_stale", "ledger": str(ledger_path), "entryIndex": index, "entryHead": git.get("head"), "scopeHead": scope.get("headSha")}
    return {"ledger": str(ledger_path), "entryIndex": index, "entrySha256": actual_hash}, None


def compute_report(project: Path, review: str, *, enforce_head: bool = True) -> tuple[dict[str, Any], int]:
    out_dir, scope = load_scope(project, review)
    matches, current = head_matches(project, scope)
    if enforce_head and not matches:
        report = {"ok": False, "failureKind": "head_changed", "scope": {"headSha": scope.get("headSha")}, "currentHead": current, "headMatches": False}
        json_dump(out_dir / "report.json", report)
        return report, 1
    review_path = out_dir / "review.json"
    if not review_path.exists():
        report = {"ok": False, "failureKind": "missing_review_json", "review": str(review_path)}
        json_dump(out_dir / "report.json", report)
        return report, 1
    review_data = json_load(review_path)
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    citation_report: dict[str, list[dict[str, Any]]] = {}
    probe_hashes: list[dict[str, Any]] = []

    candidate_symbols = scope.get("candidateSymbols", [])
    review_symbols = review_symbols_by_name(review_data)
    symbol_reports: list[dict[str, Any]] = []
    candidate_dispositions: dict[str, dict[str, Any]] = {}
    virtual_symbols: list[tuple[dict[str, Any], dict[str, Any]]] = []

    for candidate in candidate_symbols:
        matches_for_candidate = [item for item in review_symbols if candidate_matched(candidate, item)]
        if not matches_for_candidate:
            failures.append({"kind": "symbol_missing_disposition", "symbol": candidate.get("name"), "candidateId": candidate.get("id")})
        else:
            candidate_dispositions[candidate["id"]] = matches_for_candidate[0]

    for item in review_symbols:
        if item.get("declaredExtra"):
            name = symbol_name(item)
            if not name:
                failures.append({"kind": "declared_extra_missing_symbol", "entry": item})
            elif item.get("definingFile") and item.get("definingLine"):
                if not token_at_line(project, scope["headSha"], item["definingFile"], int(item["definingLine"]), name):
                    failures.append({"kind": "declared_extra_token_missing", "symbol": name})
            elif not changed_line_contains(scope, name):
                failures.append({"kind": "declared_extra_absent_from_changed_lines", "symbol": name})

    hunk_dispositions = {item.get("hunkId"): item for item in review_data.get("hunks", []) if item.get("hunkId")}
    hunk_reports: list[dict[str, Any]] = []
    for hunk in scope.get("hunks", []):
        disposition = hunk_dispositions.get(hunk.get("id"))
        hunk_report = {"id": hunk.get("id"), "requiresDisposition": hunk.get("requiresDisposition"), "accounted": False}
        if disposition:
            if disposition.get("unit") == "file-level" or disposition.get("disposition") == "file-level":
                if not disposition.get("reason"):
                    failures.append({"kind": "file_level_missing_reason", "hunkId": hunk.get("id")})
                if hunk.get("unitCandidates"):
                    failures.append({"kind": "file_level_refused_unit_exists", "hunkId": hunk.get("id")})
                hunk_report["accounted"] = True
                hunk_report["mode"] = "file-level"
            elif disposition.get("unit") == "enclosingUnit" or disposition.get("disposition") == "enclosingUnit":
                virtual, error = verify_enclosing_unit(project, scope, hunk, disposition)
                if error:
                    failures.append(error)
                else:
                    hunk_report["accounted"] = True
                    hunk_report["mode"] = "enclosingUnit"
                    virtual_symbols.append((virtual, disposition))
            else:
                failures.append({"kind": "hunk_disposition_unknown", "hunkId": hunk.get("id")})
        hunk_reports.append(hunk_report)

    path_exclusions = list(review_data.get("pathExclusions", []))
    for exclusion in path_exclusions:
        if not exclusion.get("prefix") or not exclusion.get("reason"):
            failures.append({"kind": "path_exclusion_missing_reason", "exclusion": exclusion})

    symbols_to_search: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for candidate in candidate_symbols:
        disposition = candidate_dispositions.get(candidate.get("id"))
        if disposition:
            symbols_to_search.append((candidate, disposition))
    for item in review_symbols:
        if item.get("declaredExtra"):
            symbols_to_search.append(
                (
                    {
                        "id": "s-" + sha256_text(json.dumps(item, sort_keys=True))[:12],
                        "name": symbol_name(item),
                        "symbol": symbol_name(item),
                        "source": "declared-extra",
                        "definingFile": item.get("definingFile"),
                        "definingLine": item.get("definingLine"),
                    },
                    item,
                )
            )
    symbols_to_search.extend(virtual_symbols)

    for symbol, disposition in symbols_to_search:
        name = symbol.get("name")
        if not name:
            continue
        if disposition.get("disposition") == "excluded":
            kind = disposition.get("kind")
            if kind == "too-common-token":
                failures.append({"kind": "too_common_token_bare_exclusion_removed", "symbol": name})
            if not disposition.get("reason"):
                failures.append({"kind": "symbol_exclusion_missing_reason", "symbol": name})
            symbol_reports.append({"symbol": name, "id": symbol.get("id"), "disposition": "excluded", "kind": kind, "accounted": True})
            continue
        if disposition.get("disposition", "reviewed") != "reviewed":
            failures.append({"kind": "symbol_disposition_unknown", "symbol": name, "disposition": disposition.get("disposition")})
            continue
        symbol_exclusions = path_exclusions + list(disposition.get("pathExclusions", []))
        for exclusion in disposition.get("pathExclusions", []):
            if not exclusion.get("prefix") or not exclusion.get("reason"):
                failures.append({"kind": "path_exclusion_missing_reason", "symbol": name, "exclusion": exclusion})
        raw_refs = subtract_own_ranges(grep_refs(project, scope["headSha"], name), scope, symbol)
        capped = len(raw_refs) > MAX_LISTED_REFS
        bounded_plan = disposition.get("boundedPlan") or []
        call_shapes = disposition.get("callShapes") or []
        if isinstance(call_shapes, str):
            call_shapes = [call_shapes]
        bounded_refs: list[dict[str, Any]] | None = None
        bounded_plan_report: list[dict[str, Any]] = []
        if bounded_plan:
            bounded_refs, bounded_plan_report = run_bounded_plan(project, scope, name, bounded_plan, call_shapes, failures)
            bounded_refs = subtract_own_ranges(bounded_refs, scope, symbol)
        active_refs = bounded_refs if bounded_refs is not None else raw_refs
        examined = disposition.get("refs") or []
        examined_keys: set[tuple[str, int]] = set()
        for ref in examined:
            file_path = ref.get("file")
            line_no = ref.get("line")
            if not file_path or not isinstance(line_no, int):
                failures.append({"kind": "examined_ref_invalid", "symbol": name, "ref": ref})
                continue
            if ref.get("effect") not in {"unaffected", "affected", "unknown"}:
                failures.append({"kind": "examined_ref_missing_effect", "symbol": name, "ref": ref})
            if not ref.get("note"):
                failures.append({"kind": "examined_ref_missing_note", "symbol": name, "ref": ref})
            if not token_at_line(project, scope["headSha"], file_path, line_no, name):
                failures.append({"kind": "examined_ref_token_missing", "symbol": name, "file": file_path, "line": line_no})
            examined_keys.add((file_path, line_no))
        unaccounted: list[dict[str, Any]] = []
        path_excluded_refs: list[dict[str, Any]] = []
        for ref in active_refs:
            if ref_key(ref) in examined_keys:
                continue
            exclusion = path_excluded(ref["file"], symbol_exclusions)
            if exclusion:
                path_excluded_refs.append({"file": ref["file"], "line": ref["line"], "prefix": exclusion.get("prefix")})
            else:
                unaccounted.append({"file": ref["file"], "line": ref["line"]})
        uncovered_raw_files: list[str] = []
        if bounded_plan:
            plan_paths: list[str] = []
            full_scope_plan = False
            for item in bounded_plan:
                paths = item.get("paths") or []
                if not paths:
                    full_scope_plan = True
                if isinstance(paths, str):
                    paths = [paths]
                plan_paths.extend(normalize_prefix(str(path)) for path in paths)
            for raw_ref in raw_refs:
                file_path = raw_ref["file"]
                covered_by_plan = full_scope_plan or any(is_under(file_path, prefix) for prefix in plan_paths if prefix)
                covered_by_exclusion = path_excluded(file_path, symbol_exclusions) is not None
                if not covered_by_plan and not covered_by_exclusion:
                    uncovered_raw_files.append(file_path)
            uncovered_raw_files = sorted(set(uncovered_raw_files))
        if capped and not bounded_plan:
            warnings.append({"kind": "refs_over_cap_no_bounded_plan", "symbol": name, "rawRefsFound": len(raw_refs)})
        bounded_examined_required = capped and bounded_plan and not any(ref_key(ref) in examined_keys for ref in active_refs)
        if bounded_examined_required:
            warnings.append({"kind": "bounded_plan_no_non_empty_examined_set", "symbol": name})
        symbol_reports.append(
            {
                "symbol": name,
                "id": symbol.get("id"),
                "disposition": "reviewed",
                "xref": {
                    "rawRefsFound": len(raw_refs),
                    "boundedRefsFound": len(bounded_refs) if bounded_refs is not None else None,
                    "capped": capped,
                    "listedRefs": raw_refs[:MAX_LISTED_REFS],
                    "rawBuckets": raw_ref_buckets(raw_refs),
                    "boundedPlan": bounded_plan_report,
                    "uncoveredRawFiles": uncovered_raw_files,
                },
                "examined": len(examined_keys),
                "pathExcluded": len(path_excluded_refs),
                "unaccounted": unaccounted,
                "accounted": not unaccounted and not uncovered_raw_files and not (capped and not bounded_plan) and not bounded_examined_required,
            }
        )

    claim_dispositions, claim_failures = collect_claim_dispositions(review_data)
    failures.extend(claim_failures)
    claim_reports: list[dict[str, Any]] = []
    scope_claims = {item["id"]: item for item in scope.get("claims", [])}
    for cid in claim_dispositions:
        if cid not in scope_claims:
            failures.append({"kind": "claim_unknown_id", "id": cid})
    for cid, claim in scope_claims.items():
        disposition = claim_dispositions.get(cid)
        if not disposition:
            failures.append({"kind": "claim_undispositioned", "id": cid})
            claim_reports.append({"id": cid, "disposition": None, "accounted": False})
            continue
        disp = disposition.get("disposition")
        if disp not in {"verified", "contradicted", "not-verifiable-from-diff", "non-claim"}:
            failures.append({"kind": "claim_bad_disposition", "id": cid, "disposition": disp})
        verified_citations: list[dict[str, Any]] = []
        citation_errors: list[dict[str, Any]] = []
        for citation in disposition.get("citations") or []:
            verified, error = verify_citation(project, scope, citation)
            if error:
                citation_errors.append(error)
            elif verified:
                verified_citations.append(verified)
        if citation_errors:
            failures.extend({"kind": "claim_citation_invalid", "id": cid, "error": error} for error in citation_errors)
        if disp in {"verified", "contradicted"} and not verified_citations:
            failures.append({"kind": "claim_needs_verified_citation", "id": cid})
        claim_reports.append({"id": cid, "disposition": disp, "citations": verified_citations, "accounted": True})

    findings_report: list[dict[str, Any]] = []
    for finding in review_data.get("findings", []):
        fid = finding.get("id") or "(missing-id)"
        severity = finding.get("severity")
        if severity not in {"blocking", "concern", "nit"}:
            failures.append({"kind": "finding_bad_severity", "findingId": fid})
        verified_citations: list[dict[str, Any]] = []
        citation_errors: list[dict[str, Any]] = []
        for citation in finding.get("citations") or []:
            verified, error = verify_citation(project, scope, citation)
            if error:
                citation_errors.append(error)
            elif verified:
                verified_citations.append(verified)
        if citation_errors:
            failures.extend({"kind": "finding_citation_invalid", "findingId": fid, "error": error} for error in citation_errors)
        rung = "R2"
        probe_report = None
        if finding.get("probe"):
            probe_report, error = validate_probe(project, scope, finding["probe"])
            if error:
                failures.append({"kind": error["kind"], "findingId": fid, **error})
            else:
                rung = "R3"
                probe_hashes.append(probe_report)
        elif verified_citations:
            rung = "R2"
        else:
            rung = "R1"
        if severity == "blocking" and rung == "R1":
            failures.append({"kind": "blocking_finding_unanchored", "findingId": fid})
        findings_report.append(
            {
                "id": fid,
                "severity": severity,
                "rung": rung,
                "citations": verified_citations,
                "probe": probe_report,
            }
        )
    citation_report["findings"] = findings_report

    tests_missing = bool(scope.get("testsDelta", {}).get("prodChanged") and not scope.get("testsDelta", {}).get("testsChanged") and not review_data.get("testsAcknowledgment"))
    if tests_missing:
        warnings.append({"kind": "tests_unacknowledged"})

    refs_complete = all(report.get("accounted", True) for report in symbol_reports)
    bounded_plan_uncovered = any(report.get("xref", {}).get("uncoveredRawFiles") for report in symbol_reports)
    hunks_complete = all((not report.get("requiresDisposition")) or report.get("accounted") for report in hunk_reports)
    blocking_open = any(item.get("severity") == "blocking" for item in findings_report)
    has_change_finding = any(item.get("severity") in {"blocking", "concern"} for item in findings_report)
    has_blocking_r2 = any(item.get("severity") == "blocking" and item.get("rung") in {"R2", "R3"} for item in findings_report)
    concern_only = has_change_finding and not any(item.get("severity") == "blocking" for item in findings_report)
    early_stop_allowed = has_blocking_r2 and not (refs_complete and hunks_complete)
    admissible: list[str] = ["blocked"]
    refusal_reasons: dict[str, list[str]] = {"approve": [], "request-changes": []}
    if blocking_open:
        refusal_reasons["approve"].append("blocking_open")
    if bounded_plan_uncovered:
        refusal_reasons["approve"].append("bounded_plan_uncovered_raw_path")
    if not refs_complete and not bounded_plan_uncovered:
        refusal_reasons["approve"].append("refs_unaccounted")
    if not hunks_complete:
        refusal_reasons["approve"].append("hunks_unaccounted")
    if tests_missing:
        refusal_reasons["approve"].append("tests_unacknowledged")
    if not refusal_reasons["approve"] and not failures:
        admissible.append("approve")
    if not has_change_finding:
        refusal_reasons["request-changes"].append("no_findings_for_request_changes")
    if bounded_plan_uncovered and not early_stop_allowed:
        refusal_reasons["request-changes"].append("bounded_plan_uncovered_raw_path")
    if not refs_complete and not early_stop_allowed and not bounded_plan_uncovered:
        refusal_reasons["request-changes"].append("refs_unaccounted")
    if concern_only and not refs_complete and "refs_unaccounted" not in refusal_reasons["request-changes"]:
        refusal_reasons["request-changes"].append("refs_unaccounted")
    if not hunks_complete and not early_stop_allowed:
        refusal_reasons["request-changes"].append("hunks_unaccounted")
    if not refusal_reasons["request-changes"] and not failures:
        admissible.append("request-changes")

    report = {
        "schema": SCHEMA,
        "ok": not failures,
        "headMatches": matches,
        "scope": {"headSha": scope.get("headSha"), "baseSha": scope.get("baseSha"), "mergeBaseSha": scope.get("mergeBaseSha")},
        "currentHead": current,
        "failures": failures,
        "warnings": warnings,
        "symbols": symbol_reports,
        "hunks": hunk_reports,
        "claims": claim_reports,
        "findings": findings_report,
        "probeLedgerHashes": probe_hashes,
        "testsAcknowledgmentMissing": tests_missing,
        "refsComplete": refs_complete,
        "hunksComplete": hunks_complete,
        "blastRadiusComplete": refs_complete and hunks_complete,
        "earlyStopAllowed": early_stop_allowed,
        "admissibleVerdicts": admissible,
        "refusalReasons": refusal_reasons,
    }
    json_dump(out_dir / "report.json", report)
    return report, 0 if report["ok"] else 1


def check(args: argparse.Namespace) -> None:
    project = resolve_project(args.project)
    report, code = compute_report(project, args.review)
    print_json(
        {
            "ok": code == 0,
            "report": str(review_dir(project, args.review) / "report.json"),
            "failureKind": report.get("failureKind"),
            "failures": report.get("failures", []),
            "warnings": report.get("warnings", []),
            "refusalReasons": report.get("refusalReasons", {}),
        }
    )
    if code != 0:
        raise SystemExit(code)


def status(args: argparse.Namespace) -> None:
    project = resolve_project(args.project)
    out_dir, scope = load_scope(project, args.review)
    matches, current = head_matches(project, scope)
    report_path = out_dir / "report.json"
    verdict_path = out_dir / "verdict.json"
    payload = {
        "ok": True,
        "review": slugify(args.review),
        "scope": {"headSha": scope.get("headSha"), "baseSha": scope.get("baseSha"), "mergeBaseSha": scope.get("mergeBaseSha")},
        "currentHead": current,
        "headMatches": matches,
        "artifacts": {
            "scope": str(out_dir / "scope.json"),
            "review": str(out_dir / "review.json"),
            "report": str(report_path) if report_path.exists() else None,
            "verdict": str(verdict_path) if verdict_path.exists() else None,
        },
    }
    print_json(payload)


def summarize_verdict(report: dict[str, Any]) -> dict[str, Any]:
    findings_by_severity: dict[str, int] = {"blocking": 0, "concern": 0, "nit": 0}
    rung_distribution: dict[str, int] = {"R1": 0, "R2": 0, "R3": 0}
    for finding in report.get("findings", []):
        severity = finding.get("severity")
        if severity in findings_by_severity:
            findings_by_severity[severity] += 1
        rung = finding.get("rung")
        if rung in rung_distribution:
            rung_distribution[rung] += 1
    return {
        "findingsBySeverity": findings_by_severity,
        "rungDistribution": rung_distribution,
        "refsComplete": report.get("refsComplete"),
        "hunksComplete": report.get("hunksComplete"),
        "blastRadiusComplete": report.get("blastRadiusComplete"),
    }


def first_refusal(report: dict[str, Any], verdict: str) -> str:
    reasons = report.get("refusalReasons", {}).get(verdict) or []
    return reasons[0] if reasons else "verdict_not_admissible"


def close(args: argparse.Namespace) -> None:
    project = resolve_project(args.project)
    out_dir, scope = load_scope(project, args.review)
    if args.verdict == "blocked":
        if not args.reason:
            fail("blocked_reason_required", "close --verdict blocked requires --reason")
        matches, current = head_matches(project, scope)
        payload = {
            "schema": SCHEMA,
            "ok": True,
            "verdict": "blocked",
            "reason": args.reason,
            "finished": False,
            "closedAt": utc_now(),
            "scope": {"headSha": scope.get("headSha"), "baseSha": scope.get("baseSha"), "mergeBaseSha": scope.get("mergeBaseSha")},
            "currentHead": current,
            "headMatches": matches,
            "artifactHashes": {
                "scope": sha256_file(out_dir / "scope.json"),
                "review": sha256_file(out_dir / "review.json"),
                "report": sha256_file(out_dir / "report.json"),
            },
        }
        json_dump(out_dir / "verdict.json", payload)
        print_json({"ok": True, "verdict": "blocked", "verdictFile": str(out_dir / "verdict.json"), "headMatches": matches})
        return
    matches, current = head_matches(project, scope)
    if not matches:
        fail("head_changed", "Current HEAD no longer matches scope.headSha; use a new review slug or close blocked.", {"scopeHead": scope.get("headSha"), "currentHead": current})
    report, code = compute_report(project, args.review)
    if code != 0:
        fail("check_failed", "check failed; fix review.json validity before closing", {"failures": report.get("failures", [])})
    if args.verdict not in report.get("admissibleVerdicts", []):
        kind = first_refusal(report, args.verdict)
        fail(kind, f"Verdict {args.verdict} is not admissible", {"refusalReasons": report.get("refusalReasons", {}).get(args.verdict, [])})
    blast_complete = bool(report.get("blastRadiusComplete"))
    if args.verdict == "request-changes" and report.get("earlyStopAllowed"):
        blast_complete = False
    payload = {
        "schema": SCHEMA,
        "ok": True,
        "verdict": args.verdict,
        "reason": args.reason,
        "finished": True,
        "closedAt": utc_now(),
        "scope": {"headSha": scope.get("headSha"), "baseSha": scope.get("baseSha"), "mergeBaseSha": scope.get("mergeBaseSha")},
        "currentHead": current,
        "headMatches": True,
        "blastRadiusComplete": blast_complete,
        "summary": summarize_verdict(report),
        "probeLedgerHashes": report.get("probeLedgerHashes", []),
        "artifactHashes": {
            "scope": sha256_file(out_dir / "scope.json"),
            "review": sha256_file(out_dir / "review.json"),
            "report": sha256_file(out_dir / "report.json"),
        },
    }
    json_dump(out_dir / "verdict.json", payload)
    print_json({"ok": True, "verdict": args.verdict, "verdictFile": str(out_dir / "verdict.json"), "blastRadiusComplete": blast_complete})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evidence-gated diff review helper for techne/vet.")
    sub = parser.add_subparsers(dest="command_name", required=True)

    init_p = sub.add_parser("init", help="Anchor a review scope")
    init_p.add_argument("--project", required=True, type=Path)
    init_p.add_argument("--review", required=True)
    init_p.add_argument("--base", required=True)
    init_p.add_argument("--head", default="HEAD")
    init_p.add_argument("--allow-dirty", action="store_true")
    init_p.add_argument("--claims-file", action="append", default=[])
    init_p.add_argument("--claim", action="append", default=[])
    init_p.add_argument("--no-claims", action="store_true")
    init_p.set_defaults(func=init)

    for name, func in (("check", check), ("status", status)):
        sub_p = sub.add_parser(name)
        sub_p.add_argument("--project", required=True, type=Path)
        sub_p.add_argument("--review", required=True)
        sub_p.set_defaults(func=func)

    close_p = sub.add_parser("close")
    close_p.add_argument("--project", required=True, type=Path)
    close_p.add_argument("--review", required=True)
    close_p.add_argument("--verdict", required=True, choices=["approve", "request-changes", "blocked"])
    close_p.add_argument("--reason")
    close_p.set_defaults(func=close)
    return parser


def main() -> None:
    require_posix()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
