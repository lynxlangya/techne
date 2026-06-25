#!/usr/bin/env python3
import argparse
import json
import os
import platform
import re
import subprocess
import sys
import webbrowser
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
VIEWER_ROOT = SCRIPT_ROOT / "viewer"
TEMPLATE = VIEWER_ROOT / "template.html"
MERMAID = VIEWER_ROOT / "mermaid.min.js"
SVG_PAN_ZOOM = VIEWER_ROOT / "svg-pan-zoom.min.js"


FENCE_PATTERN = re.compile(r"```(?:mermaid|mmd)\s*\n([\s\S]*?)```", re.IGNORECASE)
SCRIPT_END_PATTERN = re.compile(r"</(script)", re.IGNORECASE)
TYPE_TO_KIND = {
    "flowchart": "architecture",
    "graph": "architecture",
    "sequenceDiagram": "interaction",
    "erDiagram": "data-model",
    "stateDiagram-v2": "state-model",
    "stateDiagram": "state-model",
    "classDiagram": "type-structure",
}


def extract_mermaid(text: str) -> str:
    match = FENCE_PATTERN.search(text)
    return (match.group(1) if match else text).strip()


def assert_inside(root: Path, target: Path) -> None:
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise SystemExit(f"Indexed diagram escapes .techne/viz: {target}") from exc


def load_index(viz_dir: Path) -> dict:
    index_path = viz_dir / ".index.json"
    if not index_path.exists():
        return {"version": 1, "diagrams": []}
    return json.loads(index_path.read_text(encoding="utf-8"))


def load_diagrams(viz_dir: Path, index: dict) -> list[dict]:
    diagrams = []
    for position, item in enumerate(index.get("diagrams", [])):
        file_name = item.get("file")
        if not file_name:
            raise SystemExit(f"Diagram entry {position} has no file")
        target = (viz_dir / file_name).resolve()
        assert_inside(viz_dir, target)
        if not target.is_file():
            raise SystemExit(f"Indexed diagram file does not exist: {target}")
        raw = target.read_text(encoding="utf-8")
        source = extract_mermaid(raw)
        if not source:
            raise SystemExit(f"Indexed diagram file is empty after Mermaid extraction: {target}")
        record = dict(item)
        record["file"] = file_name
        record["type"] = record.get("type") or "flowchart"
        record["diagramKind"] = record.get("diagramKind") or TYPE_TO_KIND.get(record["type"], "unknown")
        record["raw"] = raw
        record["source"] = source
        record["exportName"] = safe_export_name(target.stem or f"diagram-{position + 1}")
        diagrams.append(record)
    return diagrams


def safe_export_name(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return name or "diagram"


def escape_script_data(value: str) -> str:
    return SCRIPT_END_PATTERN.sub(r"<\/\1", value)


def render_html(index: dict, diagrams: list[dict]) -> str:
    data = {
        "version": index.get("version", 1),
        "diagramCount": len(diagrams),
        "diagrams": diagrams,
    }
    payload = escape_script_data(json.dumps(data, ensure_ascii=False))
    html = TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "__TECHNE_MERMAID_JS__": MERMAID.read_text(encoding="utf-8"),
        "__TECHNE_SVG_PAN_ZOOM_JS__": SVG_PAN_ZOOM.read_text(encoding="utf-8"),
        "__TECHNE_VIEWER_DATA__": payload,
    }
    counts = {key: html.count(key) for key in replacements}
    invalid = [(key, count) for key, count in counts.items() if count != 1]
    if invalid:
        details = ", ".join(f"{key} found {count}" for key, count in invalid)
        raise SystemExit(f"Viewer template placeholders must appear exactly once: {details}")
    for placeholder, replacement in replacements.items():
        html = html.replace(placeholder, replacement)
    return html


def open_nonblocking(path: Path) -> None:
    url = path.resolve().as_uri()
    system = platform.system()
    stdout = subprocess.DEVNULL
    stderr = subprocess.DEVNULL
    try:
        if system == "Darwin":
            subprocess.Popen(["open", url], stdout=stdout, stderr=stderr)
            return
        if system == "Linux":
            subprocess.Popen(["xdg-open", url], stdout=stdout, stderr=stderr)
            return
        if system == "Windows":
            os.startfile(str(path.resolve()))  # type: ignore[attr-defined]
            return
    except (FileNotFoundError, OSError):
        pass
    webbrowser.open(url, new=2)


def build(project: Path) -> Path:
    project = project.resolve()
    if not project.is_dir():
        raise SystemExit(f"Project directory does not exist: {project}")
    viz_dir = (project / ".techne" / "viz").resolve()
    viz_dir.mkdir(parents=True, exist_ok=True)
    index = load_index(viz_dir)
    diagrams = load_diagrams(viz_dir, index)
    output = viz_dir / "index.html"
    output.write_text(render_html(index, diagrams), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a self-contained techne viz viewer.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--open", action="store_true", help="Open the generated viewer without blocking.")
    args = parser.parse_args()

    output = build(args.project)
    if args.open:
        open_nonblocking(output)
    print(json.dumps({"ok": True, "viewer": str(output), "opened": bool(args.open)}))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
