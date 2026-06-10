#!/usr/bin/env python3
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
VALIDATOR = SCRIPT_ROOT / "validate-mermaid.mjs"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "diagram"


def ensure_gitignore(project: Path) -> None:
    gitignore = project / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    if ".techne/" not in [line.strip() for line in existing]:
        prefix = "" if not existing or existing[-1] == "" else "\n"
        with gitignore.open("a", encoding="utf-8") as handle:
            handle.write(f"{prefix}.techne/\n")


def load_index(index_path: Path) -> dict:
    if not index_path.exists():
        return {"version": 1, "diagrams": []}
    return json.loads(index_path.read_text(encoding="utf-8"))


def validator_command(args: argparse.Namespace, project: Path) -> list[str]:
    node = shutil.which("node")
    if not node:
        raise SystemExit(
            "Node.js is required to store techne viz diagrams because store_viz.py "
            "runs validate-mermaid.mjs with provenance enforcement. Install Node.js "
            "and mermaid@11.15.0/jsdom, or set TECHNE_VIZ_NODE_MODULES."
        )
    if not VALIDATOR.is_file():
        raise SystemExit(f"Mermaid validator not found next to store_viz.py: {VALIDATOR}")
    command = [
        node,
        str(VALIDATOR),
        str(args.diagram),
        "--project",
        str(project),
        "--max-nodes",
        str(args.max_nodes),
        "--max-participants",
        str(args.max_participants),
        "--max-messages",
        str(args.max_messages),
        "--max-entities",
        str(args.max_entities),
        "--max-relationships",
        str(args.max_relationships),
        "--max-states",
        str(args.max_states),
        "--max-transitions",
        str(args.max_transitions),
        "--max-types",
        str(args.max_types),
        "--max-member-lines",
        str(args.max_member_lines),
    ]
    if args.grouped:
        command.append("--grouped")
    if args.split:
        command.append("--split")
    return command


def parse_validator_payload(text: str) -> dict | None:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def run_validator(args: argparse.Namespace, project: Path) -> dict:
    result = subprocess.run(
        validator_command(args, project),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        payload = parse_validator_payload(stderr) or parse_validator_payload(stdout)
        if payload:
            raise SystemExit("Mermaid validation failed:\n" + json.dumps(payload, indent=2, ensure_ascii=False))
        message = stderr or stdout or f"validator exited with status {result.returncode}"
        raise SystemExit("Mermaid validation failed:\n" + message)
    payload = parse_validator_payload(result.stdout)
    if not payload:
        raise SystemExit("Mermaid validation failed: validator did not return JSON")
    return payload


def derived_node_count(validation: dict) -> int | None:
    counts = validation.get("counts") or {}
    for key in ("topLevelNodes", "participants", "entities", "states", "types"):
        value = counts.get(key)
        if isinstance(value, int):
            return value
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Store a techne viz diagram in a target project.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--diagram", required=True, type=Path)
    parser.add_argument("--shape", required=True)
    parser.add_argument("--max-nodes", type=int, default=15)
    parser.add_argument("--max-participants", type=int, default=8)
    parser.add_argument("--max-messages", type=int, default=20)
    parser.add_argument("--max-entities", type=int, default=12)
    parser.add_argument("--max-relationships", type=int, default=20)
    parser.add_argument("--max-states", type=int, default=12)
    parser.add_argument("--max-transitions", type=int, default=20)
    parser.add_argument("--max-types", type=int, default=12)
    parser.add_argument("--max-member-lines", type=int, default=30)
    parser.add_argument("--grouped", action="store_true")
    parser.add_argument("--split", action="store_true")
    args = parser.parse_args()

    project = args.project.resolve()
    if not project.is_dir():
        raise SystemExit(f"Project directory does not exist: {project}")
    validation = run_validator(args, project)
    viz_dir = project / ".techne" / "viz"
    viz_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify(args.name)
    output = viz_dir / f"{slug}.md"
    diagram_text = args.diagram.read_text(encoding="utf-8")
    output.write_text(diagram_text.rstrip() + "\n", encoding="utf-8")

    index_path = viz_dir / ".index.json"
    index = load_index(index_path)
    diagrams = [item for item in index.get("diagrams", []) if item.get("file") != output.name]
    diagrams.append(
        {
            "title": args.title,
            "file": output.name,
            "diagramKind": validation.get("diagramKind"),
            "type": validation.get("mermaidType") or validation.get("diagramType"),
            "sourceFiles": validation.get("sourceFiles") or [],
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "shape": args.shape,
            "coverage": validation.get("coverage"),
            "nodeCount": derived_node_count(validation),
            "topLevelNodes": (validation.get("counts") or {}).get("topLevelNodes"),
            "grouped": args.grouped,
            "split": args.split,
        }
    )
    index["version"] = 1
    index["diagrams"] = sorted(diagrams, key=lambda item: item["title"].lower())
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ensure_gitignore(project)
    print(json.dumps({"ok": True, "diagram": str(output), "index": str(index_path)}))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
