"""Offline ClaimV2 source and account-semantics audit.

This module never builds, signs, simulates, submits or claims a transaction.
It validates normalized instruction evidence against a pinned official source
contract and returns review evidence that is never an execution approval.
"""
from __future__ import annotations

import hashlib

from application.jupiter_fee_policy import WSOL_MINT, USDC_MINT, valid_public_key
from application.jupiter_referral_verification import (
    ASSOCIATED_TOKEN_PROGRAM,
    REFERRAL_PROGRAM,
    TOKEN_PROGRAM,
    ULTRA_PROJECT,
    referral_token_address,
)

SOURCE_COMMIT = "6500f64ff004e78faa15d66446e175ede625260d"
SOURCE_REPOSITORY = "https://github.com/TeamRaccoons/referral"
SDK_SOURCE = "packages/sdk/src/referral.ts"
PROGRAM_SOURCE = "program/programs/referral/src/instructions/claim_v2.rs"
PINNED_SDK_VERSION = "0.3.0"
ACCOUNT_ORDER_AUTHORITY = "PINNED_SDK_COMPILED_IDL"
SYSTEM_PROGRAM = "11111111111111111111111111111111"
CLAIM_V2_DISCRIMINATOR = hashlib.sha256(b"global:claim_v2").digest()[:8].hex()

ACCOUNT_ROLES = (
    "payer", "project", "admin", "projectAdminTokenAccount",
    "referralAccount", "referralTokenAccount", "partner",
    "partnerTokenAccount", "mint", "systemProgram", "tokenProgram",
    "associatedTokenProgram",
)
WRITABLE_ROLES = frozenset({
    "payer", "projectAdminTokenAccount", "referralTokenAccount",
    "partnerTokenAccount",
})


class ClaimV2AuditRejected(ValueError):
    """Fixed public rejection code; input content is never echoed."""


def require(condition, code):
    if not condition:
        raise ClaimV2AuditRejected(code)


def _address(value, code="INVALID_PUBLIC_ADDRESS"):
    require(type(value) is str and valid_public_key(value), code)
    return value


def _ata(owner, mint, token_program=TOKEN_PROGRAM):
    require(token_program == TOKEN_PROGRAM, "TOKEN_2022_NOT_REVIEWED")
    try:
        from solders.pubkey import Pubkey
        owner_key = Pubkey.from_string(owner)
        program_key = Pubkey.from_string(token_program)
        mint_key = Pubkey.from_string(mint)
        ata_program = Pubkey.from_string(ASSOCIATED_TOKEN_PROGRAM)
        return str(Pubkey.find_program_address(
            [bytes(owner_key), bytes(program_key), bytes(mint_key)], ata_program
        )[0])
    except (ValueError, TypeError):
        raise ClaimV2AuditRejected("ATA_DERIVATION_FAILED") from None


def expected_accounts(identity):
    """Return the compiled IDL account order from pinned referral SDK 0.3.0."""
    require(type(identity) is dict and len(identity) <= 8, "INVALID_IDENTITY_CONTRACT")
    payer = _address(identity.get("payer"))
    project = _address(identity.get("project"))
    admin = _address(identity.get("admin"))
    referral = _address(identity.get("referral_account"))
    partner = _address(identity.get("partner"))
    mint = _address(identity.get("mint"))
    token_program = _address(identity.get("token_program"))
    require(project == ULTRA_PROJECT, "ULTRA_PROJECT_MISMATCH")
    require(token_program == TOKEN_PROGRAM, "TOKEN_2022_NOT_REVIEWED")
    require(mint in (WSOL_MINT, USDC_MINT), "UNSUPPORTED_CLAIM_MINT")
    # The permissionless payer may also be the partner that receives the claim.
    # State, authority and mint roles must still remain distinct.
    require(len({project, admin, referral, partner, mint}) == 5,
            "IDENTITY_ALIAS_NOT_ALLOWED")
    addresses = {
        "payer": payer,
        "project": project,
        "admin": admin,
        "projectAdminTokenAccount": _ata(admin, mint),
        "referralAccount": referral,
        "referralTokenAccount": referral_token_address(referral, mint),
        "partner": partner,
        "partnerTokenAccount": _ata(partner, mint),
        "mint": mint,
        "tokenProgram": token_program,
        "systemProgram": SYSTEM_PROGRAM,
        "associatedTokenProgram": ASSOCIATED_TOKEN_PROGRAM,
    }
    return tuple((role, addresses[role]) for role in ACCOUNT_ROLES)


def audit_claim_v2_instruction(evidence, identity):
    """Validate normalized ClaimV2 evidence; never treat it as claim approval."""
    require(type(evidence) is dict and len(evidence) <= 6, "INVALID_CLAIM_EVIDENCE")
    require(evidence.get("program") == REFERRAL_PROGRAM, "REFERRAL_PROGRAM_MISMATCH")
    require(evidence.get("discriminator") == CLAIM_V2_DISCRIMINATOR,
            "CLAIM_V2_DISCRIMINATOR_MISMATCH")
    accounts = evidence.get("accounts")
    require(type(accounts) is list and len(accounts) == len(ACCOUNT_ROLES),
            "CLAIM_V2_ACCOUNT_COUNT_MISMATCH")
    expected = expected_accounts(identity)
    normalized = []
    signer_roles = []
    signer_addresses = []
    for index, ((role, address), item) in enumerate(zip(expected, accounts)):
        require(type(item) is dict and set(item) == {"role", "address", "signer", "writable"},
                "INVALID_ACCOUNT_META")
        require(item["role"] == role, "CLAIM_V2_ACCOUNT_ORDER_MISMATCH")
        require(item["address"] == address, "CLAIM_V2_ACCOUNT_ADDRESS_MISMATCH")
        require(type(item["signer"]) is bool and type(item["writable"]) is bool,
                "INVALID_ACCOUNT_META_FLAGS")
        if item["signer"]:
            signer_roles.append(role)
            signer_addresses.append(item["address"])
        if role in WRITABLE_ROLES:
            require(item["writable"], "REQUIRED_WRITABLE_ACCOUNT_MISSING")
        normalized.append({"index": index, **item})
    # When payer == partner, Solana's shared account meta correctly makes both
    # semantic roles appear signed. No distinct signer address is permitted.
    require("payer" in signer_roles and set(signer_addresses) == {dict(expected)["payer"]},
            "UNEXPECTED_CLAIM_SIGNER_SET")
    require(identity.get("referral_share_bps") == 8000,
            "REFERRAL_SHARE_REQUIRES_REVIEW")
    return {
        "status": "CLAIM_V2_SOURCE_ACCOUNT_REVIEW_REQUIRED",
        "source_contract_pinned": True,
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": SOURCE_COMMIT,
        "sdk_source": SDK_SOURCE,
        "pinned_sdk_version": PINNED_SDK_VERSION,
        "account_order_authority": ACCOUNT_ORDER_AUTHORITY,
        "program_source": PROGRAM_SOURCE,
        "program": REFERRAL_PROGRAM,
        "discriminator": CLAIM_V2_DISCRIMINATOR,
        "account_count": len(normalized),
        "account_roles": normalized,
        "referral_token_model": "ULTRA_V2_CANONICAL_ATA",
        "partner_share_bps": 8000,
        "project_share_bps": 2000,
        "source_semantics_verified": True,
        "deployed_program_binary_verified": False,
        "claim_transaction_simulated": False,
        "claim_split_verified": False,
        "claim_submitted": False,
        "controlled_live_swap_approved": False,
        "production_fee_execution_enabled": False,
        "execution_ready": False,
        "fee_receipt_verified": False,
    }
