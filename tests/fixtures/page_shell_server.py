"""Local Chrome fixture: generated pages, synthetic read APIs, no upstream requests."""
import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
EMPTY = {"status": "ok", "as_of": "2026-11-11 09:00:00.000000",
         "totals": {"assets": 0, "fundamental_observations": 0, "fundamental_current": 0}, "items": []}
PAGES = {"/": "index.html", "/index.html": "index.html", "/marktdaten.html": "marktdaten.html",
         "/fundamentaldaten.html": "fundamentaldaten.html"}


class Handler(BaseHTTPRequestHandler):
    def send_body(self, body, mime):
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/codex_status.php":
            payload = {"contract_version": "mosa2_codex_status_v1", "state": "idle"}
        elif path == "/api/fundamentals.php":
            payload = EMPTY
        elif path == "/api/market.php":
            payload = {"status": "ok", "items": []}
        else:
            if path == self.server.missing:
                self.send_error(404)
                return
            file = ROOT / PAGES.get(path, path.lstrip("/"))
            if (path not in PAGES and not file.resolve().is_relative_to(ROOT / "assets")) or not file.is_file():
                self.send_error(404)
                return
            self.send_body(file.read_bytes(), (mimetypes.guess_type(file.name)[0] or "text/plain") + "; charset=utf-8")
            return
        self.send_body(json.dumps(payload).encode(), "application/json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--missing", default="")
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.missing = args.missing
        print(f"M2 fixture at http://127.0.0.1:{args.port}", flush=True)
        server.serve_forever()
