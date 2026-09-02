"""One-shot mainnet ClaimV2 execution boundary; wallet signing stays external."""
from __future__ import annotations

import argparse
import hashlib
import json
import os

from application.jupiter_claim_v2_one_shot_gate import (
    ClaimV2GateRejected, _stamp, read_gate, require, utc_now,
)
from application.jupiter_claim_v2_submission import (
    CONFIRMATION as SUBMISSION_CONFIRMATION,
    _endpoint, _signed, submit_claim,
)
from application.jupiter_referral_verification import MAINNET_GENESIS

CONFIRMATION = "I AUTHORIZE THIS ONE CLAIM V2 ON SOLANA MAINNET"
MAX_SIGNED_FILE_BYTES = 16_384


def inspect_execution_boundary(path, signed_transaction, approval_id,
                               *, environment=None, current=None):
    env = os.environ if environment is None else environment
    require(env.get("DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED", "false")
            .strip().lower() == "false", "DISABLE_APPROVAL_DURING_SUBMISSION")
    require(env.get("DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED", "false")
            .strip().lower() == "true", "CLAIM_SUBMISSION_FEATURE_DISABLED")
    require(env.get("DEXSATO_JUPITER_FEE_ENABLED", "false").strip().lower()
            == "false", "KEEP_PRODUCTION_FEES_DISABLED")
    _endpoint(env.get("SOLANA_RPC_URL", ""))
    digest = hashlib.sha256(_signed(signed_transaction)).hexdigest()
    gate = read_gate(path); current = current or utc_now()
    require(gate.get("status") == "LIVE_CLAIM_APPROVED",
            "LIVE_CLAIM_APPROVAL_REQUIRED")
    require(current <= _stamp(gate.get("expires_at", ""))
            and current <= _stamp(gate.get("approval_expires_at", "")),
            "CLAIM_LIVE_APPROVAL_EXPIRED_OR_INVALID")
    require(gate.get("approval_id") == approval_id,
            "CLAIM_LIVE_APPROVAL_ID_MISMATCH")
    require(gate.get("signed_transaction_sha256") == digest
            and gate.get("approved_signed_transaction_sha256") == digest,
            "CLAIM_APPROVED_TRANSACTION_HASH_MISMATCH")
    require(gate.get("exact_claim_raw") == "5000"
            and gate.get("maximum_claim_raw") == "5000"
            and gate.get("expected_partner_raw") == "4000"
            and gate.get("expected_project_raw") == "1000",
            "CONTROLLED_CLAIM_AMOUNT_CONTRACT_MISMATCH")
    require(gate.get("approval_count") == 1
            and gate.get("wallet_review_count") == 1
            and gate.get("submission_attempt_count") == 0
            and gate.get("submission_permitted") is True
            and gate.get("claim_submitted") is False,
            "CLAIM_GATE_ALREADY_USED_OR_UNSAFE")
    return {"status":"CONTROLLED_CLAIM_V2_SUBMISSION_REVIEW_REQUIRED",
        "gate_id":gate["gate_id"],"approval_id":approval_id,
        "signed_transaction_sha256":digest,"exact_claim_raw":"5000",
        "expected_partner_raw":"4000","expected_project_raw":"1000",
        "execution_ready":False}


def _verify_mainnet(endpoint, post):
    response = None
    try:
        if post is None:
            import requests
            post = requests.post
        response = post(endpoint, json={"jsonrpc":"2.0","id":1,
            "method":"getGenesisHash","params":[]}, timeout=(3,20),
            allow_redirects=False)
        require(response.status_code == 200, "RPC_HTTP_ERROR")
        payload = response.json()
        require(type(payload) is dict and payload.get("jsonrpc") == "2.0"
            and payload.get("id") == 1 and payload.get("error") is None
            and payload.get("result") == MAINNET_GENESIS,
            "SOLANA_MAINNET_GENESIS_MISMATCH")
        return post
    finally:
        if response is not None: response.close()


def execute_controlled_claim(path, signed_transaction, approval_id, confirmation,
                             *, environment=None, post=None, current=None):
    require(confirmation == CONFIRMATION,
            "EXPLICIT_CONTROLLED_CLAIM_CONFIRMATION_REQUIRED")
    env = os.environ if environment is None else environment
    boundary = inspect_execution_boundary(path, signed_transaction, approval_id,
        environment=env, current=current)
    endpoint = _endpoint(env.get("SOLANA_RPC_URL", ""))
    verified_post = _verify_mainnet(endpoint, post)
    result = submit_claim(path, signed_transaction, SUBMISSION_CONFIRMATION,
        approval_id, environment=env, post=verified_post, current=current)
    return {**result,"status":"CONTROLLED_CLAIM_V2_FINALIZATION_PENDING",
        "gate_id":boundary["gate_id"],"mainnet_genesis_verified":True,
        "automatic_retry":False,"execution_ready":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate",required=True)
    parser.add_argument("--signed-transaction-file",required=True)
    parser.add_argument("--approval-id",required=True)
    parser.add_argument("--confirm",required=True)
    args=parser.parse_args(argv)
    try:
        raw=open(args.signed_transaction_file,"rb").read(MAX_SIGNED_FILE_BYTES+1)
        require(len(raw)<=MAX_SIGNED_FILE_BYTES,"SIGNED_TRANSACTION_FILE_TOO_LARGE")
        signed=raw.decode("ascii").strip()
        report=execute_controlled_claim(args.gate,signed,args.approval_id,args.confirm)
        print(json.dumps(report));return 2
    except ClaimV2GateRejected as error:reason=str(error)
    except Exception:reason="CONTROLLED_CLAIM_INPUT_OR_PROVIDER_UNAVAILABLE"
    print(json.dumps({"status":"CONTROLLED_CLAIM_V2_NOT_SUBMITTED","reason":reason,
        "claim_submitted":False,"execution_ready":False}));return 1


if __name__=="__main__":raise SystemExit(main())
