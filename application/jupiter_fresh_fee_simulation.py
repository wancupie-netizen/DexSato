"""One-shot fresh 0.001 SOL fee simulation; never signs or broadcasts."""
import argparse
import json
import os
from pathlib import Path

from application.jupiter_ata_lifecycle_binding import canonical_ata
from application.jupiter_fee_balance_simulation import audit_simulation
from application.jupiter_fee_policy import WSOL_MINT, USDC_MINT
from application.jupiter_live_identity_snapshot import capture_identity
from application.jupiter_minimum_contract import MinimumContractRejected
from application.jupiter_unsigned_capture import CaptureRejected, capture

INPUT_RAW = "1000000"
FEE_BPS = 50
SLIPPAGE_BPS = 50


class FreshSimulationStageError(Exception):
    """Fixed operator-safe stage code; never contains upstream exception text."""


def run(wallet, *, environment=None, request_get=None, request_post=None, now=None):
    env = os.environ if environment is None else environment
    try:
        evidence, capture_report = capture(wallet, INPUT_RAW, FEE_BPS, SLIPPAGE_BPS,
            environment=env, request_get=request_get)
    except (CaptureRejected, MinimumContractRejected):
        raise
    except Exception:
        raise FreshSimulationStageError("FRESH_ORDER_CAPTURE_UPSTREAM_UNAVAILABLE") from None
    try:
        digest = capture_report.get("message_sha256")
        intent = {"wallet":wallet,"input_mint":WSOL_MINT,"output_mint":USDC_MINT,
            "source_token_account":canonical_ata(wallet,WSOL_MINT),
            "destination_token_account":canonical_ata(wallet,USDC_MINT),
            "message_sha256":digest}
    except Exception:
        raise FreshSimulationStageError("FRESH_INTENT_DERIVATION_FAILED") from None
    try:
        live, snapshot = capture_identity(evidence,intent,env.get("SOLANA_RPC_URL", ""),
                                          request_post=request_post)
    except MinimumContractRejected:
        raise
    except Exception:
        raise FreshSimulationStageError("FRESH_IDENTITY_SNAPSHOT_UPSTREAM_UNAVAILABLE") from None
    if live.get("status") != "LIVE_IDENTITY_REVIEW_REQUIRED":
        raise MinimumContractRejected("LIVE_IDENTITY_NOT_VERIFIED")
    try:
        simulation = audit_simulation(evidence,capture_report,live,snapshot,intent,
            environment=env,request_post=request_post,now=now)
    except MinimumContractRejected:
        raise
    except Exception:
        raise FreshSimulationStageError("FRESH_BALANCE_SIMULATION_UPSTREAM_UNAVAILABLE") from None
    return {"unsigned_evidence":evidence,"capture_report":capture_report,
            "intent":intent,"live_identity_report":live,
            "live_account_snapshot":snapshot,"simulation_report":simulation}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wallet",required=True,help="Public Solana wallet only")
    parser.add_argument("--output-dir",required=True,help="New directory; never overwritten")
    args=parser.parse_args(argv);destination=Path(args.output_dir)
    try:
        destination.mkdir(parents=False,exist_ok=False)
        result=run(args.wallet)
        names={"unsigned_evidence":"unsigned_evidence.json",
               "capture_report":"capture_report.json","intent":"public_intent.json",
               "live_identity_report":"live_identity_report.json",
               "live_account_snapshot":"live_account_snapshot.json",
               "simulation_report":"fee_balance_simulation_report.json"}
        for key,name in names.items():
            with (destination/name).open("x",encoding="utf-8") as stream:
                json.dump(result[key],stream,indent=2)
        report=result["simulation_report"]
        print(json.dumps({k:report[k] for k in
            ("status","execution_ready","fee_receipt_verified")}))
        return 2
    except (CaptureRejected,MinimumContractRejected,FreshSimulationStageError) as error: reason=str(error)
    except Exception: reason="FRESH_SIMULATION_CONFIGURATION_OR_UPSTREAM_UNAVAILABLE"
    print(json.dumps({"status":"FRESH_SIMULATION_NOT_VERIFIED","reason":reason,
                      "execution_ready":False,"fee_receipt_verified":False}))
    return 1


if __name__=="__main__":raise SystemExit(main())
