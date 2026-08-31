import copy
import json
from pathlib import Path

import pytest

from application.jupiter_minimum_contract import (
    MinimumContractRejected, audit_minimum_contract, format_raw_exact, raw_uint,
)


def sample(q=102841, slip=50, minimum="102326"):
    data = bytes.fromhex("d19853937cfed8e9") + bytes([11])
    data += (1000000).to_bytes(8, "little") + q.to_bytes(8, "little")
    data += slip.to_bytes(2, "little") + bytes(10)
    order = dict(inAmount="1000000", outAmount=str(q), slippageBps=slip,
                 otherAmountThreshold=minimum)
    route = dict(program="JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
                 name="sharedAccountsRouteV2", data_hex=data.hex(),
                 args=dict(inAmount=1000000, quotedOutAmount=q, slippageBps=slip))
    return order, dict(message_sha256="a" * 64, instructions=[route])


def audit(order, report):
    return audit_minimum_contract(order, report, report["message_sha256"])


def test_real_resolved_fixture_header_and_synthetic_order():
    report = json.loads((Path(__file__).parent / "fixtures/jupiter_v2_resolved_audit.json").read_text(encoding="utf-8-sig"))
    order, _ = sample()  # Synthetic response; not a captured provider response.
    result = audit(order, report)
    assert result["floor_candidate_raw"] == "102326"
    assert result["ceil_candidate_raw"] == "102327"
    assert result["provider_candidate_relation"] == "FLOOR_CANDIDATE_ONLY"
    assert result["enforced_minimum_raw"] is None
    for field in ("execution_ready", "enforcement_verified", "transaction_binding_verified",
                  "fee_receipt_verified", "production_formula_changed"):
        assert result[field] is False


@pytest.mark.parametrize("minimum,relation", [("102326", "FLOOR_CANDIDATE_ONLY"),
    ("102327", "CEIL_CANDIDATE_ONLY"), ("102325", "NEITHER_CANDIDATE")])
def test_hypotheses_are_not_approval(minimum, relation):
    order, report = sample(minimum=minimum)
    result = audit(order, report)
    assert result["provider_candidate_relation"] == relation
    assert result["status"] == "MINIMUM_CONTRACT_REVIEW_REQUIRED"
    assert not result["execution_ready"]


@pytest.mark.parametrize("field,value,reason", [
    ("inAmount", "999999", "ORDER_INPUT_MISMATCH"),
    ("outAmount", "102842", "ORDER_QUOTED_OUTPUT_MISMATCH"),
    ("slippageBps", 51, "ORDER_SLIPPAGE_MISMATCH"),
    ("otherAmountThreshold", "0", "INVALID_PROVIDER_MINIMUM_RANGE"),
    ("otherAmountThreshold", "102842", "INVALID_PROVIDER_MINIMUM_RANGE"),
    ("slippageBps", None, "INVALID_SLIPPAGE_BPS"),
    ("slippageBps", True, "INVALID_SLIPPAGE_BPS"),
    ("slippageBps", "50", "INVALID_SLIPPAGE_BPS"),
    ("slippageBps", -1, "INVALID_SLIPPAGE_BPS"),
    ("slippageBps", 10001, "INVALID_SLIPPAGE_BPS"),
])
def test_order_mismatch(field, value, reason):
    order, report = sample()
    order[field] = value
    with pytest.raises(MinimumContractRejected, match=reason):
        audit(order, report)


@pytest.mark.parametrize("value", [None, True, 12, 1.2, "", "-1", "1.2", "1e3", " 1", "01", "١", str(2**64)])
def test_raw_schema_rejects_lossy_or_noncanonical_inputs(value):
    order, report = sample()
    order["otherAmountThreshold"] = value
    with pytest.raises(MinimumContractRejected):
        audit(order, report)


def test_zero_slippage_is_known_and_exact():
    order, report = sample(q=123, slip=0, minimum="123")
    result = audit(order, report)
    assert result["decoded_slippage_bps"] == 0
    assert result["provider_candidate_relation"] == "BOTH_CANDIDATES"


def test_u64_arithmetic_without_float():
    q = 2**64 - 1
    floor = q * 9950 // 10000
    result = audit(*sample(q=q, minimum=str(floor)))
    assert result["floor_candidate_raw"] == str(floor)
    assert result["ceil_candidate_raw"] == str(floor + 1)
    assert raw_uint(str(q)) == q


@pytest.mark.parametrize("raw,decimals,expected", [("1", 9, "0.000000001"),
    ("9007199254740993", 0, "9007199254740993"), ("102326", 6, "0.102326"),
    ("1", 18, "0.000000000000000001"), ("0", 6, "0.000000")])
def test_audit_formatter_is_exact(raw, decimals, expected):
    assert format_raw_exact(raw, decimals) == expected


@pytest.mark.parametrize("decimals", [None, True, -1, 19, 6.0, "6"])
def test_bad_decimals(decimals):
    with pytest.raises(MinimumContractRejected, match="INVALID_DECIMALS"):
        format_raw_exact("1", decimals)


@pytest.mark.parametrize("mutation", ["args", "bytes", "variant", "duplicate", "program", "truncated"])
def test_report_mismatch(mutation):
    order, report = sample()
    route = report["instructions"][0]
    if mutation == "args": route["args"]["quotedOutAmount"] += 1
    if mutation == "bytes": route["data_hex"] = "00" + route["data_hex"][2:]
    if mutation == "variant": route["name"] = "route"
    if mutation == "duplicate": report["instructions"].append(copy.deepcopy(route))
    if mutation == "program": route["program"] = "unknown"
    if mutation == "truncated": route["data_hex"] = "00"
    with pytest.raises(MinimumContractRejected): audit(order, report)


def test_hash_mismatch_and_input_immutability():
    order, report = sample()
    before = copy.deepcopy((order, report))
    with pytest.raises(MinimumContractRejected, match="EVIDENCE_MESSAGE_HASH_MISMATCH"):
        audit_minimum_contract(order, report, "b" * 64)
    audit(order, report)
    assert (order, report) == before


def test_new_order_is_not_forced_to_match_old_quote():
    old_order, old_report = sample()
    new_order, new_report = sample(q=103000, minimum="102485")
    audit(old_order, old_report)
    audit(new_order, new_report)
    with pytest.raises(MinimumContractRejected, match="ORDER_QUOTED_OUTPUT_MISMATCH"):
        audit(old_order, new_report)
