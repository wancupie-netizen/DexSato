from scanner.database import build_market_event_record


def test_should_keep_dashboard_metadata_out_of_market_events_table():
    event = {
        "token": "BTC",
        "pair": "BTC/USDT",
        "price": "64000",
        "volume_24h": 1200000,
        "scanned_at": "2026-08-19T00:00:00+00:00",
        "price_change_24h": 2.5,
        "dex_id": "pancakeswap",
        "market_url": "https://dexscreener.com/bsc/0xpool",
    }

    record = build_market_event_record(event)

    assert record == {
        "token": "BTC",
        "pair": "BTC/USDT",
        "price": "64000",
        "volume_24h": 1200000,
        "scanned_at": "2026-08-19T00:00:00+00:00",
    }


def test_should_reject_invalid_market_event_record():
    try:
        build_market_event_record(None)
    except ValueError as error:
        assert "dictionary" in str(error)
    else:
        raise AssertionError("Invalid Market Event should be rejected.")
