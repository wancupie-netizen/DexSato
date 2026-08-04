"""
Tests for DexSato Signal Detector.

Responsibilities
----------------
Verify that detect_signals() converts normalized
market observations into the correct SignalType set.
"""

from scanner.signal_detector import detect_signals
from scanner.signal_types import SignalType


def test_should_detect_all_up_signals():

    observation = {
        "price_change_pct": 1,
        "volume_change_pct": 1,
        "liquidity_change_pct": 1,
        "market_cap_change_pct": 1,
        "fdv_change_pct": 1,
    }

    expected = {
        SignalType.PRICE_UP,
        SignalType.VOLUME_UP,
        SignalType.LIQUIDITY_UP,
        SignalType.MARKET_CAP_UP,
        SignalType.FDV_UP,
    }

    assert detect_signals(observation) == expected


def test_should_detect_all_down_signals():

    observation = {
        "price_change_pct": -1,
        "volume_change_pct": -1,
        "liquidity_change_pct": -1,
        "market_cap_change_pct": -1,
        "fdv_change_pct": -1,
    }

    expected = {
        SignalType.PRICE_DOWN,
        SignalType.VOLUME_DOWN,
        SignalType.LIQUIDITY_DOWN,
        SignalType.MARKET_CAP_DOWN,
        SignalType.FDV_DOWN,
    }

    assert detect_signals(observation) == expected


def test_should_detect_all_stable_signals():

    observation = {
        "price_change_pct": 0,
        "volume_change_pct": 0,
        "liquidity_change_pct": 0,
        "market_cap_change_pct": 0,
        "fdv_change_pct": 0,
    }

    expected = {
        SignalType.PRICE_STABLE,
        SignalType.VOLUME_STABLE,
        SignalType.LIQUIDITY_STABLE,
        SignalType.MARKET_CAP_STABLE,
        SignalType.FDV_STABLE,
    }

    assert detect_signals(observation) == expected


def test_should_ignore_none_values():

    observation = {
        "price_change_pct": 5,
        "volume_change_pct": -3,
        "liquidity_change_pct": 0,
        "market_cap_change_pct": None,
        "fdv_change_pct": 10,
    }

    expected = {
        SignalType.PRICE_UP,
        SignalType.VOLUME_DOWN,
        SignalType.LIQUIDITY_STABLE,
        SignalType.FDV_UP,
    }

    assert detect_signals(observation) == expected


def test_should_return_empty_set_when_all_values_are_none():

    observation = {
        "price_change_pct": None,
        "volume_change_pct": None,
        "liquidity_change_pct": None,
        "market_cap_change_pct": None,
        "fdv_change_pct": None,
    }

    expected = set()

    assert detect_signals(observation) == expected