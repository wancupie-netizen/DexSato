"""
Tests for AlphaRadar Founder Dashboard Service.
"""

from datetime import (
    datetime,
    timezone,
)

from adaptive.dashboard.dashboard_card import (
    create_dashboard_card,
)

from application.founder_dashboard_service import (
    FOUNDER_TOKENS,
    V1_ACTIVE_TOKENS,
    build_founder_dashboard_results,
)


def build_test_card(
    token: str,
):
    """
    Build a reusable DashboardCard.
    """

    return create_dashboard_card(
        token=token,
        decision="WATCH",
        confidence="HIGH",
        historical_success=66.67,
        seen_before=True,
        reasons=[
            "MOMENTUM",
        ],
        summary=(
            "Market intelligence available."
        ),
        last_updated=datetime.now(
            timezone.utc,
        ),
    )


def test_should_define_v1_active_tokens():
    """
    V1 production universe must contain ten approved coins.
    """

    assert V1_ACTIVE_TOKENS == (
        "BTC",
        "ETH",
        "BNB",
        "XRP",
        "SOL",
        "DOGE",
        "ADA",
        "SUI",
        "LINK",
        "AVAX",
    )

    assert len(
        V1_ACTIVE_TOKENS,
    ) == 10

    assert FOUNDER_TOKENS == (
        V1_ACTIVE_TOKENS
    )


def test_should_scan_v1_tokens_by_default():
    """
    Default service should scan the ten-coin V1 universe.
    """

    scanned_tokens: list[str] = []

    def fake_scan(
        token: str,
    ) -> dict:

        scanned_tokens.append(
            token,
        )

        return {
            "success": True,
            "dashboard": build_test_card(
                token,
            ),
        }

    results = build_founder_dashboard_results(
        scan=fake_scan,
    )

    assert scanned_tokens == list(
        V1_ACTIVE_TOKENS,
    )

    assert [
        result["token"]
        for result in results
    ] == list(
        V1_ACTIVE_TOKENS,
    )

    assert len(
        results,
    ) == 10


def test_should_accept_explicit_token_collection():
    """
    Explicit tokens should override the V1 default universe.
    """

    def fake_scan(
        token: str,
    ) -> dict:

        return {
            "success": True,
            "dashboard": build_test_card(
                token,
            ),
        }

    results = build_founder_dashboard_results(
        tokens=[
            "btc",
        ],
        scan=fake_scan,
    )

    assert results[0]["token"] == "BTC"

    assert results[0]["card"].token == "BTC"

    assert results[0]["error"] is None


def test_should_preserve_failed_coin_and_continue():
    """
    One failed coin must not hide remaining coins.
    """

    def fake_scan(
        token: str,
    ) -> dict:

        if token == "ETH":

            return {
                "success": False,
                "error": (
                    "ETH scan unavailable."
                ),
            }

        return {
            "success": True,
            "dashboard": build_test_card(
                token,
            ),
        }

    results = build_founder_dashboard_results(
        tokens=[
            "BTC",
            "ETH",
            "SOL",
        ],
        scan=fake_scan,
    )

    assert len(
        results,
    ) == 3

    assert results[0]["card"] is not None

    assert results[1]["card"] is None

    assert results[1]["error"] == (
        "ETH scan unavailable."
    )

    assert results[2]["card"] is not None


def test_should_preserve_unsupported_symbol_and_continue():
    """
    Unsupported symbols must not stop subsequent scans.
    """

    scanned_tokens: list[str] = []

    def fake_scan(
        token: str,
    ) -> dict:

        scanned_tokens.append(
            token,
        )

        return {
            "success": True,
            "dashboard": build_test_card(
                token,
            ),
        }

    results = build_founder_dashboard_results(
        tokens=[
            "BTC",
            "币安人生",
            "ETH",
        ],
        scan=fake_scan,
    )

    assert scanned_tokens == [
        "BTC",
        "ETH",
    ]

    assert len(
        results,
    ) == 3

    assert results[1]["token"] == (
        "币安人生"
    )

    assert results[1]["card"] is None

    assert (
        "unsupported characters"
        in results[1]["error"]
    )

    assert results[2]["card"] is not None