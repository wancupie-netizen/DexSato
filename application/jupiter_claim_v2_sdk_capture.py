"""Pinned official-SDK ClaimV2 construction and read-only capture boundary."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlsplit

from application.jupiter_claim_v2_capture import capture_claim_v2
from application.jupiter_claim_v2_semantics import (
    SOURCE_COMMIT, ClaimV2AuditRejected, expected_accounts, require,
)

SDK_VERSION="0.3.0"
WEB3_VERSION="1.98.4"
MAX_LOCK_BYTES=1_048_576
MAX_STDOUT_BYTES=8192
TOOL_DIR=Path(__file__).resolve().parents[1]/"tools"/"claim_v2_capture"
ATTESTATION_FILE="dependency_advisory_attestation.json"
KNOWN_PROFILE_SHA256="a3c66ca604d7a4ad9cc70209198c02a87a5203c731d5bf61f7eebd2644e11ef6"
LOCK_SHA256="f174f8bdaa2ea9096060e3714a39a4b486fafb082ec4ae1e7fa484af9b6908f4"


def strict_json_bytes(raw,maximum,code):
    require(type(raw) is bytes and len(raw)<=maximum,code)
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,"DUPLICATE_JSON_KEY")
            result[key]=value
        return result
    try:
        value=json.loads(raw.decode("utf-8-sig"),object_pairs_hook=unique,
            parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
    except ClaimV2AuditRejected:raise
    except Exception:raise ClaimV2AuditRejected(code) from None
    require(type(value) is dict,code)
    return value


def read_json(path,maximum=65_536):
    with Path(path).open("rb") as stream:raw=stream.read(maximum+1)
    return strict_json_bytes(raw,maximum,"INVALID_JSON_INPUT")


def audit_dependency_lock(path):
    path=Path(path)
    with path.open("rb") as stream:raw=stream.read(MAX_LOCK_BYTES+1)
    lock=strict_json_bytes(raw,MAX_LOCK_BYTES,"INVALID_PACKAGE_LOCK")
    require(lock.get("lockfileVersion")==3 and type(lock.get("packages")) is dict,
            "PACKAGE_LOCK_V3_REQUIRED")
    packages=lock["packages"]
    root=packages.get("")
    require(type(root) is dict and root.get("dependencies")=={
        "@jup-ag/referral-sdk":SDK_VERSION,"@solana/web3.js":WEB3_VERSION},
        "ROOT_DEPENDENCY_PIN_MISMATCH")
    sdk=packages.get("node_modules/@jup-ag/referral-sdk")
    web3=packages.get("node_modules/@solana/web3.js")
    require(type(sdk) is dict and sdk.get("version")==SDK_VERSION,
            "REFERRAL_SDK_LOCK_MISMATCH")
    require(type(web3) is dict and web3.get("version")==WEB3_VERSION,
            "WEB3_LOCK_MISMATCH")
    require(len(packages)<=512,"DEPENDENCY_COUNT_LIMIT")
    for name,item in packages.items():
        if name=="":continue
        require(type(item) is dict and type(item.get("version")) is str,
                "INVALID_LOCKED_PACKAGE")
        require(type(item.get("integrity")) is str and item["integrity"].startswith("sha512-")
                and type(item.get("resolved")) is str
                and item["resolved"].startswith("https://registry.npmjs.org/"),
                "UNPINNED_OR_NONREGISTRY_DEPENDENCY")
    return {"package_lock_sha256":hashlib.sha256(raw).hexdigest(),
            "locked_package_count":len(packages)-1,
            "sdk_version":SDK_VERSION,"web3_version":WEB3_VERSION}


def advisory_profile(payload):
    require(type(payload) is dict and payload.get("auditReportVersion")==2,
            "INVALID_NPM_AUDIT_REPORT")
    vulnerabilities=payload.get("vulnerabilities")
    metadata=payload.get("metadata")
    counts=metadata.get("vulnerabilities") if type(metadata) is dict else None
    require(type(vulnerabilities) is dict and type(counts) is dict,
            "INVALID_NPM_AUDIT_REPORT")
    require(set(counts)=={"info","low","moderate","high","critical","total"}
            and all(type(value) is int and value>=0 for value in counts.values()),
            "INVALID_NPM_AUDIT_COUNTS")
    packages={}
    for name,value in sorted(vulnerabilities.items()):
        require(type(name) is str and type(value) is dict,"INVALID_NPM_ADVISORY")
        via=value.get("via")
        require(type(via) is list and len(via)<=16,"INVALID_NPM_ADVISORY")
        sources=[]
        for item in via:
            if type(item) is str:sources.append(item)
            else:
                require(type(item) is dict and type(item.get("source")) is int,
                        "INVALID_NPM_ADVISORY")
                sources.append(str(item["source"]))
        packages[name]={"severity":value.get("severity"),
            "isDirect":value.get("isDirect"),"range":value.get("range"),
            "via":sorted(sources)}
    profile={"counts":counts,"packages":packages}
    encoded=json.dumps(profile,sort_keys=True,separators=(",",":")).encode()
    return profile,hashlib.sha256(encoded).hexdigest()


def audit_advisory_gate(tool_dir,lock,*,environment,runner=None):
    tool_dir=Path(tool_dir)
    attestation=read_json(tool_dir/ATTESTATION_FILE,maximum=16_384)
    require(set(attestation)=={"attestation_version","reviewed_at","accepted_scope",
        "package_lock_sha256","advisory_profile_sha256","reviewed_audit_sha256",
        "reviewed_dependency_tree_sha256","root_advisories","production_runtime_approved",
        "live_claim_approved","execution_ready","fee_receipt_verified"},
        "INVALID_DEPENDENCY_ATTESTATION")
    require(attestation["attestation_version"]==1
            and attestation["accepted_scope"]=="ONE_SHOT_READ_ONLY_UNSIGNED_CLAIM_V2_CAPTURE_ONLY"
            and attestation["package_lock_sha256"]==LOCK_SHA256==lock["package_lock_sha256"]
            and attestation["advisory_profile_sha256"]==KNOWN_PROFILE_SHA256,
            "DEPENDENCY_ATTESTATION_OR_LOCK_MISMATCH")
    require(attestation["production_runtime_approved"] is False
            and attestation["live_claim_approved"] is False
            and attestation["execution_ready"] is False
            and attestation["fee_receipt_verified"] is False,
            "UNSAFE_DEPENDENCY_ATTESTATION_SCOPE")
    advisories=attestation["root_advisories"]
    require(type(advisories) is list and {(item.get("source"),item.get("ghsa"))
        for item in advisories if type(item) is dict}=={
            (1103747,"GHSA-3gc7-fjrx-p6mg"),(1119441,"GHSA-w5hq-g745-h8pq")},
        "ROOT_ADVISORY_SET_MISMATCH")
    npm_name="npm.cmd" if os.name=="nt" else "npm"
    npm=shutil.which(npm_name,path=environment.get("PATH"))
    require(bool(npm),"NPM_RUNTIME_REQUIRED")
    safe_env={"PATH":environment.get("PATH",""),"npm_config_ignore_scripts":"true",
              "npm_config_audit_level":"info"}
    if os.name=="nt" and environment.get("SYSTEMROOT"):
        safe_env["SYSTEMROOT"]=environment["SYSTEMROOT"]
    execute=runner or subprocess.run
    try:
        completed=execute([npm,"audit","--json","--omit=dev","--ignore-scripts"],
            text=True,capture_output=True,timeout=45,cwd=tool_dir,env=safe_env,check=False)
    except Exception:
        raise ClaimV2AuditRejected("NPM_AUDIT_PROCESS_UNAVAILABLE") from None
    require(completed.returncode in (0,1),"NPM_AUDIT_REGISTRY_OR_PROCESS_FAILED")
    stdout=completed.stdout.encode("utf-8") if type(completed.stdout) is str else b""
    report=strict_json_bytes(stdout,MAX_LOCK_BYTES,"INVALID_NPM_AUDIT_REPORT")
    profile,digest=advisory_profile(report)
    require(digest==KNOWN_PROFILE_SHA256,"DEPENDENCY_ADVISORY_DRIFT_REQUIRES_REVIEW")
    return {"dependency_advisory_profile_sha256":digest,
            "dependency_advisory_counts":profile["counts"],
            "dependency_risk_scope":attestation["accepted_scope"],
            "root_advisory_sources":[1103747,1119441],
            "production_runtime_approved":False,"live_claim_approved":False}


def _rpc_endpoint(value):
    try:
        parsed=urlsplit(value)
        require(parsed.scheme=="https" and bool(parsed.hostname) and not parsed.username
                and not parsed.password and not parsed.fragment,
                "HTTPS_RPC_CONFIGURATION_REQUIRED")
        _=parsed.port
    except (ValueError,TypeError):
        raise ClaimV2AuditRejected("HTTPS_RPC_CONFIGURATION_REQUIRED") from None
    return value


def run_sdk(identity,*,tool_dir=TOOL_DIR,environment=None,runner=None,audit_runner=None):
    expected_accounts(identity)
    env=os.environ if environment is None else environment
    require(env.get("DEXSATO_JUPITER_FEE_ENABLED","false").strip().lower()=="false",
            "KEEP_PRODUCTION_FEES_DISABLED")
    endpoint=_rpc_endpoint(env.get("SOLANA_RPC_URL",""))
    tool_dir=Path(tool_dir)
    lock=audit_dependency_lock(tool_dir/"package-lock.json")
    advisory=audit_advisory_gate(tool_dir,lock,environment=env,runner=audit_runner)
    node=shutil.which("node",path=env.get("PATH"))
    require(bool(node),"NODE_RUNTIME_REQUIRED")
    request={key:identity[key] for key in ("payer","referral_account","mint")}
    safe_env={"PATH":env.get("PATH",""),"SOLANA_RPC_URL":endpoint,
              "NODE_NO_WARNINGS":"1"}
    if os.name=="nt" and env.get("SYSTEMROOT"):safe_env["SYSTEMROOT"]=env["SYSTEMROOT"]
    execute=runner or subprocess.run
    try:
        completed=execute([node,str(tool_dir/"build_unsigned_claim_v2.mjs")],
            input=json.dumps(request,separators=(",",":")),text=True,capture_output=True,
            timeout=45,cwd=tool_dir,env=safe_env,check=False)
    except Exception:
        raise ClaimV2AuditRejected("SDK_CONSTRUCTION_PROCESS_UNAVAILABLE") from None
    stdout=completed.stdout.encode("utf-8") if type(completed.stdout) is str else b""
    require(completed.returncode==0,"SDK_CONSTRUCTION_FAILED")
    result=strict_json_bytes(stdout,MAX_STDOUT_BYTES,"INVALID_SDK_OUTPUT")
    require(set(result)=={"status","sdk_version","source_commit","rpc_slot","transaction",
        "payer","referral_account","mint"},"INVALID_SDK_OUTPUT_FIELDS")
    require(result["status"]=="SDK_UNSIGNED_CONSTRUCTED"
            and result["sdk_version"]==SDK_VERSION and result["source_commit"]==SOURCE_COMMIT,
            "SDK_SOURCE_PIN_MISMATCH")
    for key in ("payer","referral_account","mint"):
        require(result[key]==identity[key],"SDK_IDENTITY_OUTPUT_MISMATCH")
    require(type(result["rpc_slot"]) is int and result["rpc_slot"]>0,"INVALID_SDK_RPC_SLOT")
    binding=capture_claim_v2(result["transaction"],identity,
        {"context":{"slot":result["rpc_slot"]},"accounts":{}})
    require(binding["lookup_table_count"]==0,"UNEXPECTED_SDK_LOOKUP_TABLE")
    binding.update(status="PINNED_SDK_CLAIM_V2_CAPTURE_REVIEW_REQUIRED",
        sdk_version=SDK_VERSION,web3_version=WEB3_VERSION,
        package_lock_sha256=lock["package_lock_sha256"],
        locked_package_count=lock["locked_package_count"],
        **advisory,
        sdk_construction_verified=True,rpc_read_only_construction=True,
        rpc_endpoint_recorded=False,execution_ready=False,fee_receipt_verified=False)
    capture={"status":"SDK_UNSIGNED_CAPTURED","transaction":result["transaction"],
        "identity":identity,"rpc_slot":result["rpc_slot"],
        "message_sha256":binding["message_sha256"],
        "transaction_sha256":binding["transaction_sha256"],
        "sdk_version":SDK_VERSION,"source_commit":SOURCE_COMMIT,
        "package_lock_sha256":lock["package_lock_sha256"],
        "execution_ready":False,"fee_receipt_verified":False}
    return capture,binding


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity",required=True);parser.add_argument("--output-dir",required=True)
    args=parser.parse_args(argv);destination=Path(args.output_dir)
    try:
        require(not destination.exists(),"OUTPUT_ALREADY_EXISTS")
        identity=read_json(args.identity)
        capture,binding=run_sdk(identity)
        destination.mkdir(parents=False)
        for filename,payload in (("unsigned_claim_v2_capture.json",capture),
                ("claim_v2_compiled_binding_report.json",binding)):
            with (destination/filename).open("x",encoding="utf-8") as stream:
                json.dump(payload,stream,indent=2)
        print(json.dumps({k:binding[k] for k in
            ("status","execution_ready","fee_receipt_verified")}));return 2
    except ClaimV2AuditRejected as error:reason=str(error)
    except Exception:reason="SDK_CAPTURE_INPUT_OR_OUTPUT_UNAVAILABLE"
    print(json.dumps({"status":"PINNED_SDK_CLAIM_V2_NOT_VERIFIED","reason":reason,
        "execution_ready":False,"fee_receipt_verified":False}));return 1


if __name__=="__main__":raise SystemExit(main())
