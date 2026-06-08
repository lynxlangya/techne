#!/usr/bin/env python3
import argparse
import functools
import json
import mimetypes
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote


class VizHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, viewer_root: Path, diagram_root: Path, **kwargs):
        self.viewer_root = viewer_root
        self.diagram_root = diagram_root
        super().__init__(*args, directory=str(viewer_root), **kwargs)

    def do_GET(self):
        if self.path == "/api/index":
            self.send_json(self.read_index())
            return
        if self.path.startswith("/diagrams/"):
            name = unquote(self.path.removeprefix("/diagrams/"))
            target = (self.diagram_root / name).resolve()
            if self.diagram_root not in target.parents or not target.is_file():
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "text/plain")
            self.end_headers()
            self.wfile.write(target.read_bytes())
            return
        super().do_GET()

    def read_index(self):
        index = self.diagram_root / ".index.json"
        if not index.exists():
            return {"version": 1, "diagrams": []}
        return json.loads(index.read_text(encoding="utf-8"))

    def send_json(self, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser(description="Serve stored techne viz diagrams.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()

    viewer_root = Path(__file__).resolve().parent
    diagram_root = (args.project.resolve() / ".techne" / "viz").resolve()
    diagram_root.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(VizHandler, viewer_root=viewer_root, diagram_root=diagram_root)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"http://{args.host}:{server.server_port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
