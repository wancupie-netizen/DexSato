"""Verified, read-only macro context from official BLS series."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable


BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_SOURCE_URL = "https://www.bls.gov/data/"
SERIES_IDS = (
    "CES0000000001",  # Total nonfarm employment, SA, thousands
    "LNS14000000",    # Unemployment rate, SA
    "CUUR0000SA0",    # CPI-U all items, US city average
)


def _monthly_points(series: dict[str, object]) -> list[dict[str, object]]:
    points = []
    for item in series.get("data", []):
        if not isinstance(item, dict) or str(item.get("period", "")) not in {
            f"M{month:02d}" for month in range(1, 13)
        }:
            continue
        try:
            value = float(item["value"])
        except (KeyError, TypeError, ValueError):
            # BLS may publish "-" for a period whose observation is not yet
            # available. It is missing data, not a numeric zero.
            continue
        points.append(
            {
                "key": (int(item["year"]), int(str(item["period"])[1:])),
                "label": f'{item.get("periodName", "")} {item["year"]}'.strip(),
                "value": value,
            }
        )
    return sorted(points, key=lambda point: point["key"])


def _indicator(
    *, key: str, label: str, actual: float, previous: float,
    actual_display: str, previous_display: str, reference_period: str,
    direction: str, series_id: str, unit: str,
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "actual": actual,
        "previous": previous,
        "actual_display": actual_display,
        "previous_display": previous_display,
        "reference_period": reference_period,
        "direction": direction,
        "series_id": series_id,
        "unit": unit,
        "source_url": f"https://data.bls.gov/timeseries/{series_id}",
    }


def build_fundamental_context(
    payload: dict[str, object], *, collected_at: datetime | None = None,
) -> dict[str, object]:
    """Convert official BLS observations into auditable macro context."""
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError("BLS request did not succeed.")
    raw_series = payload.get("Results", {}).get("series", [])
    by_id = {
        str(series.get("seriesID")): _monthly_points(series)
        for series in raw_series if isinstance(series, dict)
    }
    if any(len(by_id.get(series_id, [])) < 3 for series_id in SERIES_IDS[:2]):
        raise ValueError("BLS employment series are incomplete.")
    if len(by_id.get(SERIES_IDS[2], [])) < 14:
        raise ValueError("BLS CPI series needs at least 14 monthly observations.")

    jobs = by_id[SERIES_IDS[0]]
    unemployment = by_id[SERIES_IDS[1]]
    cpi = by_id[SERIES_IDS[2]]
    jobs_actual = jobs[-1]["value"] - jobs[-2]["value"]
    jobs_previous = jobs[-2]["value"] - jobs[-3]["value"]
    unemployment_actual = unemployment[-1]["value"]
    unemployment_previous = unemployment[-2]["value"]
    cpi_actual = (cpi[-1]["value"] / cpi[-13]["value"] - 1) * 100
    cpi_previous = (cpi[-2]["value"] / cpi[-14]["value"] - 1) * 100

    labor_state = "COOLING" if (
        jobs_actual < jobs_previous and unemployment_actual >= unemployment_previous
    ) else "STRENGTHENING" if (
        jobs_actual > jobs_previous and unemployment_actual <= unemployment_previous
    ) else "MIXED"
    inflation_state = (
        "COOLING" if cpi_actual < cpi_previous
        else "HEATING" if cpi_actual > cpi_previous else "STABLE"
    )
    if labor_state == "COOLING" and inflation_state == "COOLING":
        state = "MACRO_PRESSURE_EASING"
        headline = "Labour and inflation readings are cooling"
        summary = (
            "Both official series eased versus their previous readings. This can "
            "reduce macro pressure on risk assets, but does not prove the cause of "
            "the current crypto move."
        )
    elif labor_state == "STRENGTHENING" and inflation_state == "HEATING":
        state = "MACRO_PRESSURE_FIRM"
        headline = "Growth and inflation pressure remain firm"
        summary = (
            "Labour strengthened while CPI inflation increased. This may keep macro "
            "pressure on risk assets, but does not prove the cause of this price move."
        )
    else:
        state = "MIXED_MACRO_CONTEXT"
        headline = "Official macro signals are mixed"
        summary = (
            "Labour and inflation data do not point in the same direction. Treat the "
            "macro backdrop as context, not as a confirmed driver of this price move."
        )

    timestamp = collected_at or datetime.now(timezone.utc)
    indicators = [
        _indicator(
            key="PAYROLL_MOMENTUM", label="US nonfarm payroll change",
            actual=jobs_actual, previous=jobs_previous,
            actual_display=f"{jobs_actual:+.0f}K", previous_display=f"{jobs_previous:+.0f}K",
            reference_period=str(jobs[-1]["label"]), direction=labor_state,
            series_id=SERIES_IDS[0], unit="thousand jobs",
        ),
        _indicator(
            key="UNEMPLOYMENT_RATE", label="US unemployment rate",
            actual=unemployment_actual, previous=unemployment_previous,
            actual_display=f"{unemployment_actual:.1f}%",
            previous_display=f"{unemployment_previous:.1f}%",
            reference_period=str(unemployment[-1]["label"]), direction=labor_state,
            series_id=SERIES_IDS[1], unit="percent",
        ),
        _indicator(
            key="CPI_YOY", label="US CPI inflation (YoY)",
            actual=cpi_actual, previous=cpi_previous,
            actual_display=f"{cpi_actual:.1f}%", previous_display=f"{cpi_previous:.1f}%",
            reference_period=str(cpi[-1]["label"]), direction=inflation_state,
            series_id=SERIES_IDS[2], unit="percent",
        ),
    ]
    return {
        "status": "AVAILABLE",
        "collected_at": timestamp.isoformat(),
        "source": "U.S. Bureau of Labor Statistics",
        "source_url": BLS_SOURCE_URL,
        "source_tier": "PRIMARY_OFFICIAL",
        "relationship": "CONTEXTUAL",
        "causality": "NOT_ESTABLISHED",
        "state": state,
        "headline": headline,
        "summary": summary,
        "indicators": indicators,
    }


def fetch_fundamental_context(
    *, request_post: Callable[..., Any] | None = None, timeout: float = 12.0,
) -> dict[str, object]:
    """Fetch all three BLS series once for a complete dashboard snapshot."""
    if request_post is None:
        import requests

        request_post = requests.post
    response = request_post(
        BLS_API_URL, json={"seriesid": list(SERIES_IDS)}, timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("BLS returned an invalid payload.")
    return build_fundamental_context(payload)
