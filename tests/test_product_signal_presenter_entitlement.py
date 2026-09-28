from pathlib import Path

from presentation.dexsato_solana_discovery_presenter import (
    _render_live_signals_panel,
    _render_market_intelligence_panel,
    _trending_row,
)


EMPTY_FEED = {"rows": []}


def _signal(primary: str, *, direction: str = "bullish") -> dict[str, object]:
    return {
        "primary_signal": primary,
        "secondary_evidence": ["Volume ↑", "Buy pressure ↑"],
        "direction": direction,
    }


def _row(
    token_address: str,
    symbol: str,
    *,
    detected_signal: object,
) -> dict[str, object]:
    return {
        "token_address": token_address,
        "symbol": symbol,
        "name": f"{symbol} token",
        "href": f"/market/trending/{token_address}",
        "price_usd": 1.0,
        "change_1h": 2.0,
        "volume_1h_usd": 1000.0,
        "liquidity_usd": 5000.0,
        "detected_signal": detected_signal,
    }


def test_market_table_keeps_denied_row_identity_but_hides_projected_signal() -> None:
    denied = _trending_row(
        _row(
            "denied-token",
            "DENIED",
            detected_signal=None,
        ),
        1,
        liquidity_max=5000.0,
    )
    allowed = _trending_row(
        _row(
            "allowed-token",
            "ALLOWED",
            detected_signal=_signal("Allowed momentum"),
        ),
        2,
        liquidity_max=5000.0,
    )

    assert "DENIED" in denied
    assert "denied-token" in denied
    assert '<span class="dex-trending-signal">—</span>' in denied
    assert "Allowed momentum" not in denied
    assert "ALLOWED" in allowed
    assert "Allowed momentum" in allowed
    assert "dex-trending-signal is-active is-bullish" in allowed


def test_live_signals_uses_only_rows_whose_detected_signal_survives_projection() -> None:
    trending = {
        "rows": [
            _row("denied-token", "DENIED", detected_signal=None),
            _row(
                "allowed-token",
                "ALLOWED",
                detected_signal=_signal("Allowed momentum"),
            ),
        ]
    }

    html = _render_live_signals_panel(
        trending,
        EMPTY_FEED,
        EMPTY_FEED,
        EMPTY_FEED,
    )

    assert "Allowed momentum" in html
    assert "ALLOWED" in html
    assert "DENIED" not in html
    assert "denied-token" not in html
    assert 'aria-label="Recent existing DexSato signals"' in html
    assert "Six recent existing DexSato signals" not in html


def test_market_intelligence_aggregates_only_surviving_detected_signals() -> None:
    trending = {
        "rows": [
            _row("denied-token", "DENIED", detected_signal=None),
            _row(
                "allowed-token",
                "ALLOWED",
                detected_signal=_signal("Allowed momentum"),
            ),
        ]
    }

    html = _render_market_intelligence_panel(
        trending,
        EMPTY_FEED,
        EMPTY_FEED,
        EMPTY_FEED,
        dex_volume_change="—",
    )

    assert "Buying pressure leading" in html
    assert "across 1 active token signals" in html
    assert "across 2 active token signals" not in html


def test_live_signal_copy_is_quota_neutral_without_changing_internal_six_item_cap() -> None:
    source = Path("presentation/dexsato_solana_discovery_presenter.py").read_text(
        encoding="utf-8"
    )

    assert "<strong>Signals detected in the last 2h</strong>" in source
    assert "<strong>6 signals in the last 2h</strong>" not in source
    assert 'aria-label="Recent existing DexSato signals"' in source
    assert 'aria-label="Six recent existing DexSato signals"' not in source

    # The presenter still has its independent display-density cap of six.
    # A04C-03C-D changes only quota-unaware copy, not the signal engine or cap.
    assert source.count("if len(display_order) >= 6:") == 2
