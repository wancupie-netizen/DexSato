"""Read-only Ultra referral verification; never signs, creates or submits.

Layout/seeds: TeamRaccoons/referral commit 6500f64ff004e78faa15d66446e175ede625260d,
packages/sdk/src/referral.ts and program/programs/referral/src/instructions/claim_v2.rs.
Ultra V2 uses canonical ATAs with the named referral account as SPL authority.
RPC observations are trusted-provider evidence, not cryptographic state proofs.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from urllib.parse import urlsplit

from application.jupiter_fee_policy import WSOL_MINT, USDC_MINT, valid_public_key

REFERRAL_PROGRAM = "REFER4ZgmyYx9c6He5XfaTMiGfdLwRnkV4RPp9t9iF3"
ULTRA_PROJECT = "DkiqsTrw1u1bYFumumC7sCG2S8K25qc2vemJFHyW2wJc"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ASSOCIATED_TOKEN_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
MAINNET_GENESIS = "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d"
MAX_RPC_BYTES = 131072


class ReferralVerificationError(RuntimeError):
    """Safe fixed error code; never echo RPC URLs, credentials or raw data."""


def _pubkey(value):
    # SDK handles PDA/curve semantics; do not implement custom cryptography.
    try:
        from solders.pubkey import Pubkey
    except ImportError:
        raise ReferralVerificationError("REFERRAL_SDK_NOT_INSTALLED") from None
    try:
        return Pubkey.from_string(value)
    except (ValueError, TypeError):
        raise ReferralVerificationError("INVALID_PUBLIC_ADDRESS") from None


def _pda(seeds, program_id=REFERRAL_PROGRAM):
    program = _pubkey(program_id)
    return str(type(program).find_program_address(seeds, program)[0])


def referral_token_address(referral, mint):
    if mint not in (WSOL_MINT, USDC_MINT):
        raise ReferralVerificationError("UNSUPPORTED_FEE_MINT")
    # Both supported mints use Tokenkeg; referral PDAs may be off-curve.
    return _pda([bytes(_pubkey(referral)), bytes(_pubkey(TOKEN_PROGRAM)),
                 bytes(_pubkey(mint))], ASSOCIATED_TOKEN_PROGRAM)


def _data(account, owner, minimum):
    if not isinstance(account, dict) or account.get("owner") != owner or account.get("executable") is not False:
        raise ReferralVerificationError("ACCOUNT_OWNER_OR_TYPE_MISMATCH")
    encoded = account.get("data")
    if not isinstance(encoded, list) or len(encoded) != 2 or encoded[1] != "base64" or not isinstance(encoded[0], str) or len(encoded[0]) > 8192:
        raise ReferralVerificationError("INVALID_ACCOUNT_ENCODING")
    try:
        raw = base64.b64decode(encoded[0], validate=True)
    except (ValueError, TypeError):
        raise ReferralVerificationError("INVALID_ACCOUNT_ENCODING") from None
    if len(raw) < minimum:
        raise ReferralVerificationError("TRUNCATED_ACCOUNT")
    return raw


def _anchor(raw, name):
    if raw[:8] != hashlib.sha256(("account:" + name).encode()).digest()[:8]:
        raise ReferralVerificationError("ACCOUNT_DISCRIMINATOR_MISMATCH")


def _string(raw, offset):
    size = int.from_bytes(raw[offset:offset+4], "little")
    if offset + 4 > len(raw) or size > 200 or offset + 4 + size > len(raw):
        raise ReferralVerificationError("INVALID_ACCOUNT_STRING")
    try:
        value = raw[offset+4:offset+4+size].decode("utf-8")
    except UnicodeDecodeError:
        raise ReferralVerificationError("INVALID_ACCOUNT_STRING") from None
    return value, offset + 4 + size


@dataclass(frozen=True)
class ReferralObservation:
    referral_account: str
    partner: str
    partner_share_bps: int
    slot: int
    checked_at: str
    token_accounts: tuple[tuple[str, str], ...]

    def public_fields(self):
        return {"status": "RPC_ACCOUNT_VERIFIED", "referral_account": self.referral_account,
                "partner": self.partner, "project": ULTRA_PROJECT,
                "partner_share_bps": self.partner_share_bps, "slot": self.slot,
                "checked_at": self.checked_at, "commitment": "finalized",
                "token_accounts": dict(self.token_accounts), "fee_receipt_verified": False,
                "token_account_model": "ULTRA_V2_ATA", "token_authority": self.referral_account}


def validate_snapshot(referral, partner, mints, result):
    """Validate one getMultipleAccounts snapshot in our fixed requested order."""
    if not valid_public_key(referral) or not valid_public_key(partner):
        raise ReferralVerificationError("EXPECTED_PUBLIC_ADDRESSES_REQUIRED")
    if not mints or len(set(mints)) != len(mints) or any(m not in (WSOL_MINT, USDC_MINT) for m in mints):
        raise ReferralVerificationError("UNSUPPORTED_FEE_MINT")
    if not isinstance(result, dict):
        raise ReferralVerificationError("INVALID_RPC_RESULT")
    context = result.get("context")
    slot = context.get("slot") if isinstance(context, dict) else None
    accounts = result.get("value")
    if type(slot) is not int or slot <= 0 or not isinstance(accounts, list) or len(accounts) != 2 + len(mints):
        raise ReferralVerificationError("INVALID_RPC_RESULT")
    project = _data(accounts[0], REFERRAL_PROGRAM, 78)
    _anchor(project, "Project")
    if _pda([b"project", project[8:40]]) != ULTRA_PROJECT:
        raise ReferralVerificationError("ULTRA_PROJECT_PDA_MISMATCH")
    _, end = _string(project, 72)
    if end + 2 > len(project) or int.from_bytes(project[end:end+2], "little") > 10000:
        raise ReferralVerificationError("INVALID_PROJECT_SHARE")
    record = _data(accounts[1], REFERRAL_PROGRAM, 75)
    _anchor(record, "ReferralAccount")
    if record[8:40] != bytes(_pubkey(partner)):
        raise ReferralVerificationError("REFERRAL_PARTNER_MISMATCH")
    if record[40:72] != bytes(_pubkey(ULTRA_PROJECT)):
        raise ReferralVerificationError("NOT_ULTRA_REFERRAL_PROJECT")
    share = int.from_bytes(record[72:74], "little")
    # Reviewed commercial contract: 80% partner / 20% Jupiter. Changes need review.
    if share != 8000:
        raise ReferralVerificationError("REFERRAL_SHARE_REQUIRES_REVIEW")
    if record[74] == 1:
        name, _ = _string(record, 75)
        if len(name.encode()) > 32 or _pda([b"referral", bytes(_pubkey(ULTRA_PROJECT)), name.encode()]) != referral:
            raise ReferralVerificationError("REFERRAL_PDA_MISMATCH")
    elif record[74] == 0:
        raise ReferralVerificationError("ULTRA_V2_REQUIRES_NAMED_REFERRAL")
    else:
        raise ReferralVerificationError("INVALID_REFERRAL_NAME_OPTION")
    tokens = []
    for mint, account in zip(mints, accounts[2:]):
        if account is None:
            raise ReferralVerificationError("MISSING_REFERRAL_TOKEN_ACCOUNT_" + ("WSOL" if mint == WSOL_MINT else "USDC"))
        raw = _data(account, TOKEN_PROGRAM, 165)
        if len(raw) != 165 or raw[:32] != bytes(_pubkey(mint)) or raw[32:64] != bytes(_pubkey(referral)):
            raise ReferralVerificationError("TOKEN_MINT_OR_AUTHORITY_MISMATCH")
        if raw[108] != 1:
            raise ReferralVerificationError("TOKEN_ACCOUNT_NOT_INITIALIZED")
        if raw[72:76] != bytes(4) or raw[129:133] != bytes(4) or raw[121:129] != bytes(8):
            raise ReferralVerificationError("UNEXPECTED_TOKEN_DELEGATE_OR_CLOSE_AUTHORITY")
        native = int.from_bytes(raw[109:113], "little")
        if native != (1 if mint == WSOL_MINT else 0):
            raise ReferralVerificationError("TOKEN_NATIVE_STATE_MISMATCH")
        tokens.append((mint, referral_token_address(referral, mint)))
    return ReferralObservation(referral, partner, share, slot,
                               datetime.now(timezone.utc).isoformat(), tuple(tokens))


def _rpc(endpoint, method, params, request_post=None):
    if method not in {"getGenesisHash", "getMultipleAccounts"}:
        raise ReferralVerificationError("RPC_METHOD_NOT_ALLOWED")
    if request_post is None:
        import requests
        request_post = requests.post
    response = None
    try:
        response = request_post(endpoint, json={"jsonrpc": "2.0", "id": 1,
            "method": method, "params": params}, timeout=(3, 8), allow_redirects=False, stream=True)
        if response.status_code != 200:
            raise ReferralVerificationError("RPC_UNAVAILABLE")
        data = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            data.extend(chunk)
            if len(data) > MAX_RPC_BYTES:
                raise ReferralVerificationError("RPC_RESPONSE_TOO_LARGE")
        payload = json.loads(data)
        if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0" or type(payload.get("id")) is not int or payload["id"] != 1 or "error" in payload or "result" not in payload:
            raise ReferralVerificationError("INVALID_RPC_ENVELOPE")
        return payload["result"]
    except ReferralVerificationError:
        raise
    except Exception:
        raise ReferralVerificationError("RPC_UNAVAILABLE") from None
    finally:
        if response is not None:
            response.close()


def verify_referral_accounts(referral, partner, *, mints=(WSOL_MINT, USDC_MINT), rpc_url=None, request_post=None):
    if not valid_public_key(referral) or not valid_public_key(partner):
        raise ReferralVerificationError("EXPECTED_PUBLIC_ADDRESSES_REQUIRED")
    if not mints or len(set(mints)) != len(mints) or any(m not in (WSOL_MINT, USDC_MINT) for m in mints):
        raise ReferralVerificationError("UNSUPPORTED_FEE_MINT")
    endpoint = (rpc_url or os.getenv("SOLANA_RPC_URL", "")).strip()
    try:
        url = urlsplit(endpoint)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
            raise ValueError()
    except ValueError:
        raise ReferralVerificationError("HTTPS_RPC_CONFIGURATION_REQUIRED") from None
    addresses = [ULTRA_PROJECT, referral] + [referral_token_address(referral, m) for m in mints]
    if _rpc(endpoint, "getGenesisHash", [], request_post) != MAINNET_GENESIS:
        raise ReferralVerificationError("RPC_IS_NOT_SOLANA_MAINNET")
    result = _rpc(endpoint, "getMultipleAccounts", [addresses, {"encoding": "base64", "commitment": "finalized"}], request_post)
    return validate_snapshot(referral, partner, mints, result)


def main():
    # Operator-only command; reads public addresses. Does not load wallet files.
    try:
        result = verify_referral_accounts(os.getenv("DEXSATO_JUPITER_REFERRAL_ACCOUNT", ""),
            os.getenv("DEXSATO_JUPITER_REFERRAL_PARTNER", ""))
    except ReferralVerificationError as error:
        print(json.dumps({"status": "not_verified", "reason": str(error)}))
        return 1
    print(json.dumps(result.public_fields(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
