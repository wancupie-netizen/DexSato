"""Loopback-only static server for the ClaimV2 sign-only operator page."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
WEB3 = ROOT.parent / "claim_v2_capture" / "node_modules" / "@solana" / "web3.js" / "lib" / "index.iife.min.js"
ASSETS = {
    "/": (ROOT / "index.html", "text/html; charset=utf-8"),
    "/sign-only.js": (ROOT / "sign-only.js", "text/javascript; charset=utf-8"),
    "/vendor/solana-web3.js": (WEB3, "text/javascript; charset=utf-8"),
}
MAX_ASSET_BYTES = 2_000_000


class SignOnlyHandler(BaseHTTPRequestHandler):
    server_version = "DexSatoSignOnly/1"

    def _headers(self, status, content_type="text/plain; charset=utf-8", length=0):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'none'; img-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()

    def _host_allowed(self):
        host = self.headers.get("Host", "").lower()
        return host == "localhost" or host.startswith("localhost:") or host == "127.0.0.1" or host.startswith("127.0.0.1:")

    def _serve(self, *, head=False):
        if not self._host_allowed():
            self._headers(403)
            return
        path = urlsplit(self.path).path
        asset = ASSETS.get(path)
        if asset is None:
            self._headers(404)
            return
        source, content_type = asset
        try:
            size = source.stat().st_size
            if size <= 0 or size > MAX_ASSET_BYTES or not source.is_file():
                raise OSError
            data = b"" if head else source.read_bytes()
        except OSError:
            self._headers(503)
            return
        self._headers(200, content_type, size)
        if not head:
            self.wfile.write(data)

    def do_GET(self):
        self._serve()

    def do_HEAD(self):
        self._serve(head=True)

    def do_POST(self):
        self._headers(405)

    def do_PUT(self):
        self._headers(405)

    def do_DELETE(self):
        self._headers(405)

    def log_message(self, format, *args):
        return


def make_server(port):
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("INVALID_PORT")
    return ThreadingHTTPServer(("127.0.0.1", port), SignOnlyHandler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not WEB3.is_file():
        parser.error("pinned web3 browser bundle is missing; run npm ci --ignore-scripts in tools/claim_v2_capture")
    server = make_server(args.port)
    print(f"ClaimV2 sign-only page: http://127.0.0.1:{server.server_port}/")
    print("GET-only loopback server; no RPC, approval, or submission endpoint exists.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
