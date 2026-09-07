"""Loopback-only static server for the ClaimV2 sign-only operator page."""

from __future__ import annotations

import argparse
import json
import re
import secrets
import threading
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
SAFE_CODE=re.compile(r"^[A-Z][A-Z0-9_]{2,95}$")

class JitStageRejected(RuntimeError):
    def __init__(self,stage,reason="UNCLASSIFIED_FAILURE"):
        self.stage=stage;self.reason=reason;super().__init__(stage)

def _reason(error):
    value=str(error)
    if error.__class__.__name__.endswith("Rejected") and SAFE_CODE.fullmatch(value):
        return value
    if isinstance(error,FileExistsError):return "OUTPUT_ALREADY_EXISTS"
    if isinstance(error,(KeyError,TypeError,ValueError)):return "INTERNAL_CONTRACT_MISMATCH"
    if isinstance(error,OSError):return "LOCAL_IO_UNAVAILABLE"
    return "UNCLASSIFIED_FAILURE"

def _prepare_payload(config):
    from application.jupiter_claim_v2_fresh_reconstruction import _read_json,_write_exclusive
    from application.jupiter_claim_v2_jit_handoff import (
        HANDOFF_CONFIRMATION,prepare_jit_handoff)
    from application.jupiter_claim_v2_one_shot_gate import CONFIRMATION_PHRASE
    try:
        identity=_read_json(config["identity"]);closure=_read_json(config["evidence_closure"])
        boundary=_read_json(config["boundary"])
    except Exception as error:raise JitStageRejected("JIT_INPUT_READ_FAILED",_reason(error)) from None
    try:
        report=prepare_jit_handoff(identity,closure,boundary,config["output_dir"],
            config["gate"],CONFIRMATION_PHRASE,HANDOFF_CONFIRMATION)
    except Exception as error:
        raise JitStageRejected("JIT_FRESH_RECONSTRUCTION_FAILED",_reason(error)) from None
    output=Path(config["output_dir"])
    try:_write_exclusive(output/"jit_signing_handoff.json",report)
    except Exception as error:raise JitStageRejected("JIT_HANDOFF_WRITE_FAILED",_reason(error)) from None
    try:
        capture=_read_json(output/"unsigned_claim_v2_capture.json");gate=_read_json(config["gate"])
    except Exception as error:
        raise JitStageRejected("JIT_RESPONSE_ARTIFACT_READ_FAILED",_reason(error)) from None
    return {"status":"JIT_UNSIGNED_ARTIFACTS_READY","capture":capture,
        "gate":gate,"handoff":report}


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
        connect = "'self'" if getattr(self.server, "jit_config", None) else "'none'"
        self.send_header("Content-Security-Policy",
                         f"default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src {connect}; img-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
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
        if urlsplit(self.path).path == "/jit/session":
            if not self._host_allowed() or not getattr(self.server,"jit_config",None):
                self._headers(404);return
            data=json.dumps({"status":"JIT_SESSION_READY","token":self.server.jit_token,
                "used":self.server.jit_used}).encode()
            self._headers(200,"application/json; charset=utf-8",len(data));self.wfile.write(data);return
        self._serve()

    def do_HEAD(self):
        self._serve(head=True)

    def do_POST(self):
        if urlsplit(self.path).path != "/jit/prepare" or not getattr(self.server,"jit_config",None):
            self._headers(405);return
        origin=self.headers.get("Origin","")
        expected=f"http://127.0.0.1:{self.server.server_port}"
        if (not self._host_allowed() or origin!=expected or
            self.headers.get("X-DexSato-JIT-Token","")!=self.server.jit_token or
            self.headers.get("Content-Length","0")!="0"):
            self._headers(403);return
        with self.server.jit_lock:
            if self.server.jit_used:self._headers(409);return
            self.server.jit_used=True
        try:
            data=json.dumps(_prepare_payload(self.server.jit_config),
                separators=(",",":")).encode()
            self._headers(200,"application/json; charset=utf-8",len(data));self.wfile.write(data)
        except Exception as error:
            stage=error.stage if isinstance(error,JitStageRejected) else "JIT_HTTP_HANDLER_FAILED"
            reason=error.reason if isinstance(error,JitStageRejected) else "UNCLASSIFIED_FAILURE"
            data=json.dumps({"status":"JIT_UNSIGNED_ARTIFACTS_NOT_VERIFIED",
                "stage":stage,"reason":reason,"transaction_submitted":False,
                "execution_ready":False}).encode()
            self._headers(409,"application/json; charset=utf-8",len(data));self.wfile.write(data)

    def do_PUT(self):
        self._headers(405)

    def do_DELETE(self):
        self._headers(405)

    def log_message(self, format, *args):
        return


def make_server(port,jit_config=None):
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("INVALID_PORT")
    server=ThreadingHTTPServer(("127.0.0.1", port), SignOnlyHandler)
    server.jit_config=jit_config;server.jit_token=secrets.token_urlsafe(32)
    server.jit_used=False;server.jit_lock=threading.Lock();return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    for name in ("identity","evidence-closure","boundary","output-dir","gate"):
        parser.add_argument("--jit-"+name)
    args = parser.parse_args(argv)
    if not WEB3.is_file():
        parser.error("pinned web3 browser bundle is missing; run npm ci --ignore-scripts in tools/claim_v2_capture")
    names=("identity","evidence_closure","boundary","output_dir","gate")
    values={name:getattr(args,"jit_"+name) for name in names}
    provided=[bool(value) for value in values.values()]
    if any(provided) and not all(provided):parser.error("all --jit-* arguments are required together")
    server = make_server(args.port,values if all(provided) else None)
    print(f"ClaimV2 sign-only page: http://127.0.0.1:{server.server_port}/")
    print("Loopback sign-only server; no signed-byte upload, approval, or submission endpoint exists.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
