"""
Tests for DexSato Observation Builder.
"""

from scanner.observation_builder import (
    percent_change,
    calculate_observation,
)


# ==================================================
# percent_change()
# ==================================================

def test_should_calculate_positive_percent_change():

    assert percent_change(110, 100) == 10.0


def test_should_calculate_negative_percent_change():

    assert percent_change(90, 100) == -10.0


def test_should_return_zero_percent_change():

    assert percent_change(100, 100) == 0.0


def test_should_return_none_when_current_is_none():

    assert percent_change(None, 100) is None


def test_should_return_none_when_previous_is_none():

    assert percent_change(100, None) is None


def test_should_return_none_when_previous_is_zero():

    assert percent_change(100, 0) is None


# ==================================================
# calculate_observation()
# ==================================================

def test_should_build_complete_observation():

    current = {

        "price": 110,

        "liquidity": 220,

        "volume_24h": 330,

        "market_cap": 440,

        "fdv": 550,
    }

    previous = {

        "price": 100,

        "liquidity": 200,

        "volume_24h": 300,

        "market_cap": 400,

        "fdv": 500,
    }

    observation = calculate_observation(
        "BTC",
        current,
        previous,
    )

    assert observation == {

        "token": "BTC",

        "price_change_pct": 10.0,

        "liquidity_change_pct": 10.0,

        "volume_change_pct": 10.0,

        "market_cap_change_pct": 10.0,

        "fdv_change_pct": 10.0,
    }


def test_should_support_none_values():

    current = {

        "price": None,

        "liquidity": 100,

        "volume_24h": None,

        "market_cap": 300,

        "fdv": None,
    }

    previous = {

        "price": 100,

        "liquidity": 100,

        "volume_24h": 100,

        "market_cap": 300,

        "fdv": 100,
    }

    observation = calculate_observation(
        "ETH",
        current,
        previous,
    )

    assert observation["price_change_pct"] is None

    assert observation["volume_change_pct"] is None

    assert observation["fdv_change_pct"] is None

    assert observation["liquidity_change_pct"] == 0.0

    assert observation["market_cap_change_pct"] == 0.0


def test_should_support_negative_changes():

    current = {

        "price": 80,

        "liquidity": 160,

        "volume_24h": 240,

        "market_cap": 320,

        "fdv": 400,
    }

    previous = {

        "price": 100,

        "liquidity": 200,

        "volume_24h": 300,

        "market_cap": 400,

        "fdv": 500,
    }

    observation = calculate_observation(
        "SOL",
        current,
        previous,
    )

    assert observation["price_change_pct"] == -20.0

    assert observation["liquidity_change_pct"] == -20.0

    assert observation["volume_change_pct"] == -20.0

    assert observation["market_cap_change_pct"] == -20.0

    assert observation["fdv_change_pct"] == -20.0