#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Store a techne viz diagram in a target project.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--diagram", required=True, type=Path)
    parser.add_argument("--shape", required=True)
    parser.add_argument("--type", default="flowchart")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--coverage", default="grounded")
    parser.add_argument("--node-count", type=int)
    parser.add_argument("--max-nodes", type=int, default=15)
    parser.add_argument("--grouped", action="store_true")
    parser.add_argument("--split", action="store_true")
    args = parser.parse_args()

    project = args.project.resolve()
    if not project.is_dir():
        raise SystemExit(f"Project directory does not exist: {project}")
    if args.node_count and args.node_count > args.max_nodes and not (args.grouped or args.split):
        raise SystemExit(
            f"Node count {args.node_count} exceeds max {args.max_nodes}; group into subgraphs or mark --grouped/--split"
        )
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
            "type": args.type,
            "sourceFiles": args.source,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "shape": args.shape,
            "coverage": args.coverage,
            "nodeCount": args.node_count,
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
    main()
