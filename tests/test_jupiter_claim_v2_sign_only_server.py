import http.client
import threading
from pathlib import Path

from tools.claim_v2_sign_only import server as sign_server


def request(server, method, path, *, host=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    connection.putrequest(method, path, skip_host=host is not None)
    if host is not None:
        connection.putheader("Host", host)
    for key,value in (headers or {}).items():connection.putheader(key,value)
    connection.endheaders()
    response = connection.getresponse()
    body = response.read()
    headers = dict(response.getheaders())
    connection.close()
    return response.status, headers, body


def running_server(monkeypatch, tmp_path):
    page = tmp_path / "index.html"
    page.write_text("sign-only", encoding="utf-8")
    monkeypatch.setattr(sign_server, "ASSETS", {
        "/": (page, "text/html; charset=utf-8"),
    })
    instance = sign_server.make_server(0)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    return instance, thread


def test_server_binds_only_ipv4_loopback():
    instance = sign_server.make_server(0)
    try:
        assert instance.server_address[0] == "127.0.0.1"
    finally:
        instance.server_close()


def test_allowlisted_get_has_strict_no_store_headers(monkeypatch, tmp_path):
    instance, thread = running_server(monkeypatch, tmp_path)
    try:
        status, headers, body = request(instance, "GET", "/")
        assert status == 200 and body == b"sign-only"
        assert headers["Cache-Control"] == "no-store"
        assert headers["X-Frame-Options"] == "DENY"
        assert "connect-src 'none'" in headers["Content-Security-Policy"]
    finally:
        instance.shutdown(); thread.join(); instance.server_close()


def test_unknown_path_and_non_loopback_host_are_rejected(monkeypatch, tmp_path):
    instance, thread = running_server(monkeypatch, tmp_path)
    try:
        assert request(instance, "GET", "/capture.json")[0] == 404
        assert request(instance, "GET", "/", host="attacker.example")[0] == 403
    finally:
        instance.shutdown(); thread.join(); instance.server_close()


def test_all_mutating_http_methods_are_rejected(monkeypatch, tmp_path):
    instance, thread = running_server(monkeypatch, tmp_path)
    try:
        for method in ("POST", "PUT", "DELETE"):
            assert request(instance, method, "/")[0] == 405
    finally:
        instance.shutdown(); thread.join(); instance.server_close()


def test_server_and_page_contain_no_secret_or_transaction_submission_path():
    sources = [Path(sign_server.__file__).read_text(encoding="utf-8")]
    root = Path(sign_server.__file__).parent
    sources.extend((root / name).read_text(encoding="utf-8")
                   for name in ("index.html", "sign-only.js"))
    forbidden = ("sendTransaction", "sendRawTransaction", "privateKey",
                 "secretKey", "seedPhrase", "/api/", "send_signature")
    assert all(term not in source for source in sources for term in forbidden)

def test_jit_endpoint_requires_exact_origin_token_and_is_one_shot(monkeypatch,tmp_path):
 config={"identity":"i","evidence_closure":"e","boundary":"b",
  "output_dir":"o","gate":"g"}
 monkeypatch.setattr(sign_server,"_prepare_payload",lambda value:
  {"status":"JIT_UNSIGNED_ARTIFACTS_READY","capture":{},"gate":{},"handoff":{}})
 instance=sign_server.make_server(0,config);thread=threading.Thread(
  target=instance.serve_forever,daemon=True);thread.start()
 try:
  origin=f"http://127.0.0.1:{instance.server_port}"
  assert request(instance,"POST","/jit/prepare")[0]==403
  headers={"Origin":origin,"X-DexSato-JIT-Token":instance.jit_token,
   "Content-Length":"0"}
  status,_,body=request(instance,"POST","/jit/prepare",headers=headers)
  assert status==200 and b"JIT_UNSIGNED_ARTIFACTS_READY" in body
  assert request(instance,"POST","/jit/prepare",headers=headers)[0]==409
 finally:instance.shutdown();thread.join();instance.server_close()

def test_stage_diagnostics_never_copy_exception_prose(monkeypatch):
 monkeypatch.setattr(sign_server,"_prepare_payload",
  lambda config:(_ for _ in ()).throw(RuntimeError("https://secret-rpc.example/key")))
 instance=sign_server.make_server(0,{"identity":"i"});thread=threading.Thread(
  target=instance.serve_forever,daemon=True);thread.start()
 try:
  headers={"Origin":f"http://127.0.0.1:{instance.server_port}",
   "X-DexSato-JIT-Token":instance.jit_token,"Content-Length":"0"}
  status,_,body=request(instance,"POST","/jit/prepare",headers=headers)
  assert status==409 and b"JIT_HTTP_HANDLER_FAILED" in body
  assert b"secret-rpc" not in body
 finally:instance.shutdown();thread.join();instance.server_close()

def test_safe_reason_whitelists_codes_only():
 class DomainRejected(RuntimeError):pass
 assert sign_server._reason(DomainRejected("SDK_CONSTRUCTION_FAILED"))=="SDK_CONSTRUCTION_FAILED"
 assert sign_server._reason(DomainRejected("secret prose"))=="UNCLASSIFIED_FAILURE"
