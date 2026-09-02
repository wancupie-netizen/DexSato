import hashlib
import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

from application import jupiter_claim_v2_sdk_capture as sdk
from application.jupiter_claim_v2_semantics import ClaimV2AuditRejected
from application.jupiter_fee_policy import WSOL_MINT
from application.jupiter_referral_verification import TOKEN_PROGRAM,ULTRA_PROJECT

PARTNER="J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs"
REFERRAL="5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ"
ADMIN="D8cy77BBepLMngZx6ZukaTff5hCt1HrWyKk3Hnd9oitf"


def identity():return {"payer":PARTNER,"project":ULTRA_PROJECT,"admin":ADMIN,
    "referral_account":REFERRAL,"partner":PARTNER,"mint":WSOL_MINT,
    "token_program":TOKEN_PROGRAM,"referral_share_bps":8000}


def lock(tmp_path,*,sdk_version="0.3.0",web3_version="1.98.4",integrity=True):
    def package(version,name):
        value={"version":version,"resolved":f"https://registry.npmjs.org/{name}/-/x.tgz"}
        if integrity:value["integrity"]="sha512-AAAA"
        return value
    payload={"name":"capture","version":"0.0.0","lockfileVersion":3,"requires":True,
      "packages":{"":{"dependencies":{"@jup-ag/referral-sdk":"0.3.0",
        "@solana/web3.js":"1.98.4"}},
        "node_modules/@jup-ag/referral-sdk":package(sdk_version,"referral-sdk"),
        "node_modules/@solana/web3.js":package(web3_version,"web3")}}
    path=tmp_path/"package-lock.json";path.write_text(json.dumps(payload),encoding="utf-8")
    return path


def audit_payload():
    specs={
      "@coral-xyz/anchor":("moderate",False,"*",["@coral-xyz/borsh","@solana/web3.js"]),
      "@coral-xyz/borsh":("moderate",False,"*",["@solana/web3.js"]),
      "@jup-ag/referral-sdk":("high",True,"*",["@coral-xyz/anchor","@solana/spl-token","@solana/web3.js"]),
      "@solana/buffer-layout-utils":("high",False,"*",["@solana/web3.js","bigint-buffer"]),
      "@solana/spl-token":("high",False,"*",["@solana/buffer-layout-utils","@solana/web3.js"]),
      "@solana/web3.js":("moderate",True,"<=0.0.0-pr-29130 || 0.0.4 - 1.98.4",["jayson"]),
      "bigint-buffer":("high",False,"*",[{"source":1103747}]),
      "jayson":("moderate",False,">=2.0.6",["uuid"]),
      "uuid":("moderate",False,"<11.1.1",[{"source":1119441}])}
    vulnerabilities={name:{"name":name,"severity":severity,"isDirect":direct,
      "via":via,"effects":[],"range":version_range,"nodes":[],"fixAvailable":False}
      for name,(severity,direct,version_range,via) in specs.items()}
    return {"auditReportVersion":2,"vulnerabilities":vulnerabilities,
      "metadata":{"vulnerabilities":{"info":0,"low":0,"moderate":5,"high":4,
        "critical":0,"total":9},"dependencies":{"prod":75,"dev":0,"optional":23,
        "peer":21,"peerOptional":0,"total":98}}}


def prepare_gate(tmp_path,monkeypatch):
    path=lock(tmp_path);lock_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(sdk,"LOCK_SHA256",lock_hash)
    attestation={"attestation_version":1,"reviewed_at":"2026-09-01",
      "accepted_scope":"ONE_SHOT_READ_ONLY_UNSIGNED_CLAIM_V2_CAPTURE_ONLY",
      "package_lock_sha256":lock_hash,"advisory_profile_sha256":sdk.KNOWN_PROFILE_SHA256,
      "reviewed_audit_sha256":"a"*64,"reviewed_dependency_tree_sha256":"b"*64,
      "root_advisories":[{"source":1103747,"ghsa":"GHSA-3gc7-fjrx-p6mg"},
                           {"source":1119441,"ghsa":"GHSA-w5hq-g745-h8pq"}],
      "production_runtime_approved":False,"live_claim_approved":False,
      "execution_ready":False,"fee_receipt_verified":False}
    (tmp_path/sdk.ATTESTATION_FILE).write_text(json.dumps(attestation),encoding="utf-8")
    monkeypatch.setattr(sdk.shutil,"which",lambda name,**k:
                        "C:/node/node.exe" if name.startswith("node") else "C:/node/npm.cmd")
    audit_runner=lambda *a,**k:SimpleNamespace(returncode=1,
        stdout=json.dumps(audit_payload()),stderr="")
    return audit_runner


def unsigned_transaction():
    helper=runpy.run_path(str(Path(__file__).with_name("test_jupiter_claim_v2_capture.py")))
    return helper["transaction"]()


def test_lock_v3_exact_versions_and_integrities_are_attested(tmp_path):
    path=lock(tmp_path);report=sdk.audit_dependency_lock(path)
    assert report["sdk_version"]=="0.3.0" and report["web3_version"]=="1.98.4"
    assert report["locked_package_count"]==2
    assert report["package_lock_sha256"]==hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("change,code",[
    ({"sdk_version":"0.3.1"},"REFERRAL_SDK_LOCK_MISMATCH"),
    ({"web3_version":"1.98.3"},"WEB3_LOCK_MISMATCH"),
    ({"integrity":False},"UNPINNED_OR_NONREGISTRY_DEPENDENCY"),
])
def test_dependency_drift_or_missing_integrity_fails_closed(tmp_path,change,code):
    with pytest.raises(ClaimV2AuditRejected,match=code):sdk.audit_dependency_lock(lock(tmp_path,**change))


def test_pinned_sdk_output_is_reaudited_by_e4b(monkeypatch,tmp_path):
    audit_runner=prepare_gate(tmp_path,monkeypatch);encoded=unsigned_transaction();seen={}
    def runner(command,**kwargs):
        seen.update(command=command,kwargs=kwargs)
        request=json.loads(kwargs["input"])
        output={"status":"SDK_UNSIGNED_CONSTRUCTED","sdk_version":"0.3.0",
          "source_commit":"6500f64ff004e78faa15d66446e175ede625260d","rpc_slot":123,
          "transaction":encoded,"payer":request["payer"],
          "referral_account":request["referral_account"],"mint":request["mint"]}
        return SimpleNamespace(returncode=0,stdout=json.dumps(output),stderr="")
    capture,report=sdk.run_sdk(identity(),tool_dir=tmp_path,
      environment={"PATH":"safe","SOLANA_RPC_URL":"https://rpc.example/key",
                   "DEXSATO_JUPITER_FEE_ENABLED":"false","UNRELATED_SECRET":"never"},
                   runner=runner,audit_runner=audit_runner)
    assert report["status"]=="PINNED_SDK_CLAIM_V2_CAPTURE_REVIEW_REQUIRED"
    assert report["sdk_construction_verified"] is True
    assert report["compiled_account_binding_verified"] is True
    assert report["rpc_endpoint_recorded"] is False
    assert report["dependency_advisory_counts"]=={
      "info":0,"low":0,"moderate":5,"high":4,"critical":0,"total":9}
    assert report["production_runtime_approved"] is False
    assert report["live_claim_approved"] is False
    assert capture["transaction"]==encoded
    assert seen["kwargs"]["env"]=={"PATH":"safe","SOLANA_RPC_URL":"https://rpc.example/key",
                                    "NODE_NO_WARNINGS":"1"}
    assert seen["kwargs"]["timeout"]==45 and seen["kwargs"]["check"] is False
    assert report["execution_ready"] is False and report["fee_receipt_verified"] is False


def test_enabled_production_fee_and_non_https_rpc_stop_before_process(monkeypatch,tmp_path):
    lock(tmp_path);called=[]
    monkeypatch.setattr(sdk.shutil,"which",lambda *a,**k:"node")
    for environment,code in (({"DEXSATO_JUPITER_FEE_ENABLED":"true"},"KEEP_PRODUCTION_FEES_DISABLED"),
      ({"DEXSATO_JUPITER_FEE_ENABLED":"false","SOLANA_RPC_URL":"http://rpc"},
       "HTTPS_RPC_CONFIGURATION_REQUIRED")):
        with pytest.raises(ClaimV2AuditRejected,match=code):
            sdk.run_sdk(identity(),tool_dir=tmp_path,environment=environment,
                        runner=lambda *a,**k:called.append(1))
    assert called==[]


def test_sdk_pin_identity_and_signed_or_malformed_output_fail_closed(monkeypatch,tmp_path):
    audit_runner=prepare_gate(tmp_path,monkeypatch)
    base={"status":"SDK_UNSIGNED_CONSTRUCTED","sdk_version":"0.3.0",
      "source_commit":"6500f64ff004e78faa15d66446e175ede625260d","rpc_slot":123,
      "transaction":unsigned_transaction(),"payer":PARTNER,"referral_account":REFERRAL,"mint":WSOL_MINT}
    for mutation,code in (({"sdk_version":"0.3.1"},"SDK_SOURCE_PIN_MISMATCH"),
                           ({"payer":ADMIN},"SDK_IDENTITY_OUTPUT_MISMATCH")):
        output={**base,**mutation}
        runner=lambda *a,_output=output,**k:SimpleNamespace(returncode=0,stdout=json.dumps(_output),stderr="")
        with pytest.raises(ClaimV2AuditRejected,match=code):
            sdk.run_sdk(identity(),tool_dir=tmp_path,
                environment={"PATH":"x","SOLANA_RPC_URL":"https://rpc.example",
                             "DEXSATO_JUPITER_FEE_ENABLED":"false"},runner=runner,
                             audit_runner=audit_runner)


def test_new_advisory_severity_or_registry_failure_blocks_capture(monkeypatch,tmp_path):
    prepare_gate(tmp_path,monkeypatch);lock_report=sdk.audit_dependency_lock(tmp_path/"package-lock.json")
    changed=audit_payload();changed["metadata"]["vulnerabilities"]["high"]=5
    changed["metadata"]["vulnerabilities"]["total"]=10
    changed["vulnerabilities"]["new-package"]={"severity":"high","isDirect":False,
      "range":"*","via":[{"source":9999999}]}
    runner=lambda *a,**k:SimpleNamespace(returncode=1,stdout=json.dumps(changed),stderr="")
    with pytest.raises(ClaimV2AuditRejected,match="DEPENDENCY_ADVISORY_DRIFT_REQUIRES_REVIEW"):
        sdk.audit_advisory_gate(tmp_path,lock_report,
            environment={"PATH":"x"},runner=runner)
    runner=lambda *a,**k:SimpleNamespace(returncode=2,stdout="{}",stderr="secret registry")
    with pytest.raises(ClaimV2AuditRejected,match="NPM_AUDIT_REGISTRY_OR_PROCESS_FAILED"):
        sdk.audit_advisory_gate(tmp_path,lock_report,
            environment={"PATH":"x"},runner=runner)


def test_node_builder_has_no_keypair_signing_or_submission_api():
    source=(Path(sdk.__file__).resolve().parents[1]/"tools"/"claim_v2_capture"/
            "build_unsigned_claim_v2.mjs").read_text(encoding="utf-8")
    for forbidden in ("Keypair","sendTransaction","sendRawTransaction",
                      "sendAndConfirm",".sign(","secretKey"):
        assert forbidden not in source
