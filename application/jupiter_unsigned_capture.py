"""Operator-only unsigned evidence capture; no signing or execution paths.

Fixed GET /swap/v2/order only. RPC verifier is read-only. No endpoint override,
receiver, payer, wallet key, server flag mutation or pending-order insertion.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from application.jupiter_fee_policy import read_fee_policy, validate_fee_response, WSOL_MINT, USDC_MINT, valid_public_key
from application.jupiter_referral_verification import verify_referral_accounts, ReferralVerificationError
from application.jupiter_swap_service import _transaction_parts, _base58_bytes
from application.jupiter_fee_transaction_harness import amount
from application.jupiter_instruction_decoder import inspect_transaction

ENDPOINT = "https://api.jup.ag/swap/v2/order"
MAX_BYTES = 65536
FIELDS = {"inputMint", "outputMint", "inAmount", "outAmount", "otherAmountThreshold",
          "swapMode", "slippageBps", "referralAccount", "feeMint", "feeBps", "router",
          "transaction", "taker", "gasless", "signatureFeePayer", "signatureFeeLamports",
          "prioritizationFeeLamports", "rentFeeLamports", "lastValidBlockHeight",
          "platformFee"}


class CaptureRejected(ValueError):
    pass


def get_order(params, api_key, request_get=None):
    response = None
    try:
        response = (request_get or requests.get)(ENDPOINT, params=params,
            headers={"x-api-key": api_key, "accept": "application/json"},
            timeout=(3, 15), stream=True, allow_redirects=False)
        if response.status_code != 200:
            raise CaptureRejected("JUPITER_HTTP_ERROR")
        raw = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            raw.extend(chunk)
            if len(raw) > MAX_BYTES:
                raise CaptureRejected("JUPITER_RESPONSE_TOO_LARGE")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise CaptureRejected("DUPLICATE_JSON_KEY")
                result[key] = value
            return result
        payload = json.loads(raw, object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(CaptureRejected("INVALID_JSON_NUMBER")))
        if not isinstance(payload, dict) or payload.get("errorCode") is not None or payload.get("error"):
            raise CaptureRejected("JUPITER_ORDER_BUILD_ERROR")
        # Never copy request IDs, URLs, headers, raw errors or unknown fields.
        return {key: value for key, value in payload.items() if key in FIELDS}
    except CaptureRejected:
        raise
    except Exception:
        raise CaptureRejected("JUPITER_CAPTURE_UNAVAILABLE") from None
    finally:
        if response is not None:
            response.close()


def capture(wallet, input_raw, fee_bps, slippage_bps, *, environment=None, request_get=None):
    env = os.environ if environment is None else environment
    if env.get("DEXSATO_JUPITER_FEE_ENABLED", "false").strip().lower() != "false":
        raise CaptureRejected("KEEP_PRODUCTION_FEES_DISABLED")
    if not valid_public_key(wallet) or not 1000000 <= amount(input_raw) <= 1000000000:
        raise CaptureRejected("INVALID_CAPTURE_INTENT")
    if type(slippage_bps) is not int or not 0 <= slippage_bps <= 100:
        raise CaptureRejected("INVALID_CAPTURE_SLIPPAGE")
    policy = read_fee_policy({"DEXSATO_JUPITER_FEE_ENABLED": "true",
        "DEXSATO_JUPITER_REFERRAL_ACCOUNT": env.get("DEXSATO_JUPITER_REFERRAL_ACCOUNT", ""),
        "DEXSATO_JUPITER_REFERRAL_FEE_BPS": str(fee_bps)})
    key = env.get("JUPITER_API_KEY", "").strip()
    if not key:
        raise CaptureRejected("JUPITER_API_KEY_REQUIRED")
    referral = verify_referral_accounts(policy.referral_account,
        env.get("DEXSATO_JUPITER_REFERRAL_PARTNER", ""), rpc_url=env.get("SOLANA_RPC_URL", ""))
    params = {"inputMint": WSOL_MINT, "outputMint": USDC_MINT, "amount": input_raw,
        "swapMode": "ExactIn", "slippageBps": str(slippage_bps),
        "excludeRouters": "jupiterz,dflow,okx", **policy.request_parameters()}
    quote = get_order(params, key, request_get)
    def validate(payload):
        if any(payload.get(k) != v for k,v in {"inputMint": WSOL_MINT, "outputMint": USDC_MINT,
            "inAmount": input_raw, "swapMode": "ExactIn", "router": "metis"}.items()):
            raise CaptureRejected("PROVIDER_INTENT_MISMATCH")
        threshold = amount(payload.get("otherAmountThreshold"))
        if threshold > amount(payload.get("outAmount")):
            raise CaptureRejected("INVALID_PROVIDER_THRESHOLD")
        if type(payload.get("slippageBps")) is not int or payload["slippageBps"] != slippage_bps:
            raise CaptureRejected("PROVIDER_SLIPPAGE_MISMATCH")
        validate_fee_response(policy, payload, input_mint=WSOL_MINT, output_mint=USDC_MINT)
        platform = payload.get("platformFee")
        if not isinstance(platform, dict) or platform.get("feeBps") != policy.fee_bps:
            raise CaptureRejected("PLATFORM_FEE_EVIDENCE_MISMATCH")
        platform_amount = platform.get("amount")
        if platform_amount is not None:
            try:
                valid_amount = (amount(platform_amount)
                    == amount(input_raw) * policy.fee_bps // 10000)
            except Exception:
                valid_amount = False
            if not valid_amount:
                raise CaptureRejected("PLATFORM_FEE_EVIDENCE_MISMATCH")
    validate(quote)
    if quote.get("transaction") not in (None, ""):
        raise CaptureRejected("QUOTE_CONTAINS_TRANSACTION")
    order = get_order({**params, "taker": wallet}, key, request_get)
    validate(order)
    if order.get("taker") != wallet or order.get("gasless") is not False or order.get("signatureFeePayer") != wallet:
        raise CaptureRejected("UNREVIEWED_SIGNER_OR_SPONSORSHIP")
    _, signatures, _, signers, keys, _ = _transaction_parts(order.get("transaction"))
    if signers != [_base58_bytes(wallet)] or not keys or keys[0] != _base58_bytes(wallet) or any(s != bytes(64) for s in signatures):
        raise CaptureRejected("ORDER_MUST_BE_UNSIGNED_SINGLE_WALLET")
    report = inspect_transaction(order["transaction"])
    report.update(captured_at=datetime.now(timezone.utc).isoformat(),
        referral_observation=referral.public_fields(), capture_only=True,
        input_raw=input_raw, fee_bps=policy.fee_bps, slippage_bps=slippage_bps)
    return {"quote": quote, "order": order}, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wallet", required=True)
    parser.add_argument("--input-raw", required=True, help="SOL lamports; capture only")
    parser.add_argument("--fee-bps", required=True, type=int)
    parser.add_argument("--slippage-bps", required=True, type=int)
    parser.add_argument("--output-dir", required=True, help="New directory; never overwritten")
    args = parser.parse_args(argv)
    destination = Path(args.output_dir)
    # Reserve a new directory BEFORE upstream work; never overwrite user files.
    try:
        destination.mkdir(parents=False, exist_ok=False)
        evidence, report = capture(args.wallet, args.input_raw, args.fee_bps, args.slippage_bps)
        for name, value in (("unsigned_evidence.json", evidence), ("decoder_report.json", report)):
            with (destination/name).open("x", encoding="utf-8") as stream:
                json.dump(value, stream, indent=2)
        print(json.dumps({"status":"CAPTURED_REVIEW_REQUIRED", "execution_ready":False,
                          "fee_receipt_verified":False}))
        return 2
    except CaptureRejected as error:
        print(json.dumps({"status":"REJECTED", "reason":str(error)}))
    except ReferralVerificationError as error:
        print(json.dumps({"status":"REJECTED", "reason":str(error)}))
    except Exception:
        print(json.dumps({"status":"REJECTED", "reason":"CAPTURE_CONFIGURATION_OR_IO_ERROR"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
