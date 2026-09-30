from application.solana_universe_registry import (
    SOLANA_UNIVERSE,
    SOLANA_UNIVERSE_BY_MINT,
    is_solana_universe_asset,
    solana_universe_asset,
)


EXPECTED_SYMBOLS = [
    "JUP", "RAY", "JTO", "PYTH", "KMNO", "ORCA", "DRIFT",
    "RENDER", "HNT", "GRASS", "HONEY",
    "BONK", "WIF", "PENGU", "FARTCOIN", "TRUMP", "PNUT", "MEW", "BOME", "GIGA",
]


def test_solana_universe_is_locked_core_20_in_display_order():
    assert [asset["symbol"] for asset in SOLANA_UNIVERSE] == EXPECTED_SYMBOLS
    assert len(SOLANA_UNIVERSE) == 20


def test_solana_universe_symbols_and_mints_are_unique():
    symbols = [asset["symbol"] for asset in SOLANA_UNIVERSE]
    mints = [asset["mint"] for asset in SOLANA_UNIVERSE]
    assert len(symbols) == len(set(symbols))
    assert len(mints) == len(set(mints))
    assert len(SOLANA_UNIVERSE_BY_MINT) == 20


def test_full_canonical_mints_are_locked_for_final_verification_assets():
    expected = {
        "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
        "GRASS": "Grass7B4RdKfBCjTKgSqnXkqjwiGvQyFbuSCUJr3XXjs",
        "GIGA": "63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9",
    }
    actual = {asset["symbol"]: asset["mint"] for asset in SOLANA_UNIVERSE}
    for symbol, mint in expected.items():
        assert actual[symbol] == mint


def test_exact_mint_lookup_never_uses_ticker_matching():
    bonk_mint = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    asset = solana_universe_asset(bonk_mint)
    assert asset is not None
    assert asset["symbol"] == "BONK"
    assert is_solana_universe_asset(bonk_mint) is True
    assert is_solana_universe_asset("BONK") is False
    assert solana_universe_asset("") is None