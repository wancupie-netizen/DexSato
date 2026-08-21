from presentation.dexsato_admin_presenter import render_admin_system_page


def test_admin_system_page_groups_internal_operational_cards():
    snapshot = {
        "generated_at": "2026-08-22T04:00:00+00:00",
        "total_coins": 3,
        "available_coins": 2,
        "coins": [
            {"available": True, "decision": "ALERT"},
            {"available": True, "decision": "REVIEW"},
            {"available": False, "decision": "UNAVAILABLE"},
        ],
        "provider_health": {
            "status": "RECOVERED",
            "providers": [{
                "provider": "DexScreener", "status": "RECOVERED",
                "logical_requests": 6, "retries": 1, "failures": 0,
            }],
        },
    }
    status = {
        "overall_health": "HEALTHY",
        "snapshot": {"status": "FRESH"},
        "latest_run": {"telegram_status": "SENT"},
        "tasks": [{"installed": True, "last_result_status": "SUCCESS"}],
    }

    html = render_admin_system_page(snapshot, system_status=status)

    assert "Admin Operations" in html
    assert "System Operations" in html
    assert "Market State" in html
    assert "System Health" in html
    assert "Provider Operations" in html
    assert "DexScreener" in html
    assert "6 requests · 1 retries · 0 failures" in html
    assert "2/3" in html
    assert "Internal operations console" in html
    assert 'href="/"' in html


def test_admin_system_page_handles_missing_provider_activity():
    html = render_admin_system_page(
        {"coins": [], "total_coins": 0, "available_coins": 0},
        system_status={},
    )

    assert "No provider activity recorded for this snapshot." in html
    assert "No Activity" in html


def test_admin_overall_health_does_not_mask_failed_telegram_or_scheduler():
    html = render_admin_system_page(
        {
            "coins": [], "total_coins": 0, "available_coins": 0,
            "provider_health": {"status": "HEALTHY", "providers": []},
        },
        system_status={
            "overall_health": "HEALTHY",
            "snapshot": {"status": "FRESH"},
            "latest_run": {"telegram_status": "FAILED"},
            "tasks": [],
        },
    )

    assert '<span>Overall Health</span><strong class="state-attention">Attention</strong>' in html


def test_admin_overall_health_marks_required_data_failure_as_degraded():
    html = render_admin_system_page(
        {
            "coins": [], "total_coins": 0, "available_coins": 0,
            "provider_health": {"status": "DEGRADED", "providers": []},
        },
        system_status={
            "overall_health": "HEALTHY",
            "snapshot": {"status": "FRESH"},
            "latest_run": {"telegram_status": "SENT"},
            "tasks": [{"installed": True, "last_result_status": "SUCCESS"}],
        },
    )

    assert '<span>Overall Health</span><strong class="state-degraded">Degraded</strong>' in html
