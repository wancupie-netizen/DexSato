"""Founder-only Content Control Center services.

This module reads existing DexSato snapshot facts and prepares social drafts.
It does not calculate, override, or mutate any DexSato market decision.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import random
import re
import secrets
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

COOKIE_NAME = "dexsato_content_session"
SESSION_TTL_SECONDS = 60 * 60 * 12
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def content_control_configured() -> bool:
    return bool(_env("CONTENT_CONTROL_PASSWORD") and _env("CONTENT_CONTROL_SESSION_SECRET"))


def ai_enabled() -> bool:
    return bool(_env("OPENAI_API_KEY"))


def ai_model() -> str:
    return _env("CONTENT_CONTROL_AI_MODEL") or "gpt-5.6"


def password_matches(candidate: object) -> bool:
    expected = _env("CONTENT_CONTROL_PASSWORD")
    supplied = str(candidate or "")
    return bool(expected) and secrets.compare_digest(supplied, expected)


def create_session_token() -> str:
    secret = _env("CONTENT_CONTROL_SESSION_SECRET")
    if not secret:
        raise RuntimeError("CONTENT_CONTROL_SESSION_SECRET is not configured.")
    expires = int(time.time()) + SESSION_TTL_SECONDS
    payload = str(expires)
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def session_is_valid(token: object) -> bool:
    secret = _env("CONTENT_CONTROL_SESSION_SECRET")
    raw = str(token or "")
    if not secret or "." not in raw:
        return False
    expires_raw, supplied_signature = raw.split(".", 1)
    try:
        expires = int(expires_raw)
    except ValueError:
        return False
    if expires <= int(time.time()):
        return False
    expected_signature = hmac.new(
        secret.encode(), expires_raw.encode(), hashlib.sha256
    ).hexdigest()
    return secrets.compare_digest(supplied_signature, expected_signature)


def find_market(snapshot: dict[str, object], token: object) -> dict[str, object] | None:
    coins = snapshot.get("coins")
    if not isinstance(coins, list):
        return None
    normalized = str(token or "").strip().upper()
    for item in coins:
        if not isinstance(item, dict):
            continue
        if str(item.get("token", "")).strip().upper() == normalized:
            return item
    return None


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list(value: object, limit: int | None = None) -> list[object]:
    rows = value if isinstance(value, list) else []
    return rows if limit is None else rows[:limit]


def _metric_value(metric: object, key: str = "value") -> object:
    return metric.get(key) if isinstance(metric, dict) else None


def _clean_rules(value: object, limit: int = 8) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for row in _list(value, limit):
        if isinstance(row, dict):
            result.append(
                {
                    "label": row.get("label"),
                    "status": row.get("status"),
                    "actual": row.get("actual"),
                    "requirement": row.get("requirement"),
                }
            )
    return result


def _clean_context_notes(value: object, limit: int = 8) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for row in _list(value, limit):
        if isinstance(row, dict):
            result.append({"type": row.get("type"), "text": row.get("text")})
    return result


def _clean_changes(value: object, limit: int = 10) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for row in _list(value, limit):
        if isinstance(row, dict):
            result.append(
                {
                    "label": row.get("label"),
                    "previous": row.get("previous"),
                    "current": row.get("current"),
                }
            )
    return result


def _clean_scan_history(value: object, limit: int = 6) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    rows = _list(value)
    for row in rows[-limit:]:
        if isinstance(row, dict):
            result.append(
                {
                    "recorded_at": row.get("recorded_at"),
                    "decision": row.get("decision"),
                    "technical_bias": row.get("technical_bias"),
                    "rsi_14": row.get("rsi_14"),
                    "relative_volume": row.get("relative_volume"),
                }
            )
    return result


def _clean_fundamental_indicators(value: object, limit: int = 8) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for row in _list(value, limit):
        if isinstance(row, dict):
            result.append(
                {
                    "label": row.get("label"),
                    "reference_period": row.get("reference_period"),
                    "direction": row.get("direction"),
                    "actual_display": row.get("actual_display"),
                    "previous_display": row.get("previous_display"),
                    "source": row.get("source"),
                }
            )
    return result


def _clean_catalysts(value: object, limit: int = 6) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for row in _list(value, limit):
        if isinstance(row, dict):
            result.append(
                {
                    "category": row.get("category"),
                    "title": row.get("title"),
                    "source": row.get("source"),
                    "published_at": row.get("published_at"),
                }
            )
    return result


def _clean_venues(value: object, limit: int = 3) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for row in _list(value, limit):
        if isinstance(row, dict):
            result.append(
                {
                    "name": row.get("name"),
                    "type": row.get("type"),
                    "pair": row.get("pair"),
                    "volume_24h": row.get("volume_24h"),
                    "liquidity": row.get("liquidity"),
                }
            )
    return result


def build_content_facts(coin: dict[str, object]) -> dict[str, object]:
    """Build a comprehensive read-only packet from already-computed DexSato output."""
    evidence = _dict(coin.get("technical_evidence"))
    metrics = _dict(evidence.get("metrics"))
    outlook = _dict(evidence.get("outlook"))
    brief = _dict(coin.get("trader_decision_brief"))
    change = _dict(coin.get("change_since_previous"))
    fundamental = _dict(coin.get("fundamental_context"))
    catalysts = _dict(coin.get("market_catalysts"))

    rsi = _dict(metrics.get("rsi_14"))
    ema_50 = _dict(metrics.get("ema_50"))
    ema_200 = _dict(metrics.get("ema_200"))
    relative_volume = _dict(metrics.get("relative_volume_20"))
    structure = _dict(metrics.get("market_structure"))

    reasons = coin.get("reasons")
    if str(coin.get("decision") or "").upper() == "REFERENCE":
        reasons = coin.get("reference_evidence")

    facts: dict[str, object] = {
        "core_market": {
            "token": coin.get("token"),
            "pair": coin.get("pair"),
            "asset_class": coin.get("asset_class"),
            "chain": coin.get("chain"),
            "price": coin.get("price"),
            "price_change_24h": coin.get("price_change_24h"),
            "volume_24h": coin.get("volume_24h"),
            "liquidity": coin.get("liquidity"),
            "market_cap": coin.get("market_cap"),
            "source": coin.get("source"),
            "scanned_at": coin.get("scanned_at"),
            "available": coin.get("available"),
        },
        "decision": {
            "decision": coin.get("decision"),
            "confidence": coin.get("confidence"),
            "summary": coin.get("summary"),
            "reasons": _list(reasons, 8),
            "risk_note": coin.get("risk_note"),
            "seen_before": coin.get("seen_before"),
        },
        "technical": {
            "status": coin.get("technical_evidence_status"),
            "timeframe": evidence.get("timeframe"),
            "source": evidence.get("source"),
            "candle_closed_at": evidence.get("candle_closed_at"),
            "bias": outlook.get("bias"),
            "outlook_summary": outlook.get("summary"),
            "rsi_14": rsi.get("value"),
            "rsi_previous": rsi.get("previous"),
            "rsi_state": rsi.get("state"),
            "rsi_direction": rsi.get("direction"),
            "ema_50": ema_50.get("value"),
            "ema_50_distance_pct": ema_50.get("price_distance_pct"),
            "ema_200": ema_200.get("value"),
            "ema_200_distance_pct": ema_200.get("price_distance_pct"),
            "relative_volume_20": relative_volume.get("value"),
            "market_structure": structure.get("state"),
            "confirmation": _clean_rules(outlook.get("confirmation")),
            "invalidation": _clean_rules(outlook.get("invalidation")),
        },
        "trader_brief": {
            "status": brief.get("status"),
            "state": brief.get("state"),
            "headline": brief.get("headline"),
            "summary": brief.get("summary"),
            "next_action": brief.get("next_action"),
            "pending_confirmation": _clean_rules(brief.get("pending_confirmation")),
            "invalidation": _clean_rules(brief.get("invalidation")),
            "context_notes": _clean_context_notes(brief.get("context_notes")),
            "policy": brief.get("policy"),
        },
        "change_since_previous": {
            "status": change.get("status"),
            "headline": change.get("headline"),
            "changes": _clean_changes(change.get("changes")),
            "policy": change.get("policy"),
        },
        "recent_scan_history": _clean_scan_history(coin.get("recent_scan_history")),
        "fundamental_context": {
            "status": coin.get("fundamental_context_status"),
            "headline": fundamental.get("headline"),
            "summary": fundamental.get("summary"),
            "source": fundamental.get("source"),
            "indicators": _clean_fundamental_indicators(fundamental.get("indicators")),
        },
        "market_catalysts": {
            "status": coin.get("market_catalysts_status"),
            "headline": catalysts.get("headline"),
            "summary": catalysts.get("summary"),
            "catalysts": _clean_catalysts(catalysts.get("catalysts")),
        },
        "trading_venues": _clean_venues(coin.get("trading_venues")),
    }
    return facts


def _fact(facts: dict[str, object], section: str, key: str) -> object:
    container = facts.get(section)
    return container.get(key) if isinstance(container, dict) else None



CONTENT_TYPE_ALIASES = {
    "current_update": "current_update",
    "current market read": "current_update",
    "market read": "current_update",
    "current": "current_update",
    "what_changed": "what_changed",
    "what changed": "what_changed",
    "change": "what_changed",
    "trader_brief": "trader_brief",
    "trader brief": "trader_brief",
    "technical_update": "technical_update",
    "technical update": "technical_update",
    "technical": "technical_update",
    "risk_focus": "risk_focus",
    "risk / invalidation": "risk_focus",
    "risk focus": "risk_focus",
    "risk": "risk_focus",
    "fundamental_context": "fundamental_context",
    "fundamental context": "fundamental_context",
    "fundamental": "fundamental_context",
    "catalyst_update": "catalyst_update",
    "catalyst update": "catalyst_update",
    "catalyst": "catalyst_update",
}

STYLE_ALIASES = {
    "trader": "trader",
    "trader - natural": "trader",
    "trader natural": "trader",
    "professional": "professional",
    "educational": "educational",
    "concise": "concise",
}

LENGTH_ALIASES = {
    "short": "short",
    "medium": "medium",
    "full": "full",
    "near 280 characters": "full",
    "long": "full",
}


def _resolve_alias(value: object, mapping: dict[str, str], fallback: str) -> str:
    normalized = str(value or "").strip().lower()
    return mapping.get(normalized, fallback)


def _safe_sentence_limit(text: str, maximum: int = 280) -> str:
    """Never return a mid-rule/mid-sentence string slice."""
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip().strip('"')
    if len(cleaned) <= maximum and cleaned and cleaned[-1] in ".!?":
        return cleaned

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    accepted = ""
    for sentence in sentences:
        candidate = (accepted + " " + sentence).strip()
        if len(candidate) <= maximum:
            accepted = candidate
        else:
            break

    if accepted and accepted[-1] in ".!?":
        return accepted

    # If there is no complete sentence, return empty so the caller can use a
    # content-specific deterministic fallback rather than a broken fragment.
    return ""


def _market_identity(facts: dict[str, object]) -> str:
    """Resolve market identity from flat/nested content facts without inference."""
    core_market = facts.get("core_market")
    core_market = core_market if isinstance(core_market, dict) else {}
    candidates = [
        core_market.get("pair"),
        core_market.get("token"),
        facts.get("pair"),
        facts.get("market"),
        facts.get("symbol"),
        facts.get("token"),
    ]

    raw_decision = facts.get("decision")
    if isinstance(raw_decision, dict):
        candidates.extend([
            raw_decision.get("pair"),
            raw_decision.get("market"),
            raw_decision.get("symbol"),
            raw_decision.get("token"),
        ])

    for value in candidates:
        text = str(value or "").strip()
        if text and text.upper() not in {"MARKET", "UNKNOWN", "NONE"}:
            return text.upper()

    return "MARKET"

def _normalized_decision_fields(facts: dict[str, object]) -> tuple[str, str, str, str]:
    """Support both flat and nested decision schemas without printing raw dicts."""
    raw_decision = facts.get("decision")
    decision = ""
    confidence = ""
    summary = ""
    risk_note = ""

    if isinstance(raw_decision, dict):
        decision = str(
            raw_decision.get("decision")
            or raw_decision.get("DECISION")
            or ""
        ).strip()
        confidence = str(
            raw_decision.get("confidence")
            or raw_decision.get("CONFIDENCE")
            or ""
        ).strip()
        summary = str(
            raw_decision.get("summary")
            or raw_decision.get("SUMMARY")
            or ""
        ).strip()
        risk_note = str(
            raw_decision.get("risk_note")
            or raw_decision.get("RISK_NOTE")
            or ""
        ).strip()
    else:
        decision = str(raw_decision or "").strip()

    if not confidence:
        confidence = str(facts.get("confidence") or "").strip()
    if not summary:
        summary = str(facts.get("summary") or "").strip()
    if not risk_note:
        risk_note = str(facts.get("risk_note") or "").strip()

    return (
        decision.upper() or "UNKNOWN",
        confidence.upper() or "UNKNOWN",
        summary,
        risk_note,
    )

def _fmt_number(value: object, suffix: str = "") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{number:.2f}".rstrip("0").rstrip(".") + suffix


def _technical_facts(facts: dict[str, object]) -> tuple[str, str, str]:
    technical = facts.get("technical")
    technical = technical if isinstance(technical, dict) else {}
    bias = str(
        technical.get("bias") or facts.get("technical_bias") or ""
    ).replace("_", " ").upper()
    rsi = _fmt_number(technical.get("rsi_14") or facts.get("rsi_14"))
    volume = _fmt_number(
        technical.get("relative_volume_20") or facts.get("relative_volume_20"),
        "x",
    )
    return bias, rsi, volume


def _rule_text(rules: object) -> str:
    if not isinstance(rules, list):
        return ""
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        label = str(rule.get("label") or "").strip()
        actual = str(rule.get("actual") or "").strip()
        requirement = str(rule.get("requirement") or "").strip()
        status = str(rule.get("status") or "").strip()
        pieces = [piece for piece in (label, status, actual, requirement) if piece]
        if pieces:
            return " - ".join(pieces)
    return ""


def _first_rule(rules: object) -> dict[str, object]:
    if not isinstance(rules, list):
        return {}
    for rule in rules:
        if isinstance(rule, dict):
            return rule
    return {}


def _as_complete_sentence(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    return text if text[-1] in ".!?" else f"{text}."


def _fallback_draft(facts: dict[str, object], content_type: str, style: str = "trader") -> str:
    """Content-specific fallback. It always returns a usable complete draft."""
    token = _market_identity(facts)
    decision, confidence, decision_summary, normalized_risk_note = (
        _normalized_decision_fields(facts)
    )
    bias, rsi, volume = _technical_facts(facts)

    brief = facts.get("trader_brief")
    brief = brief if isinstance(brief, dict) else {}
    change = facts.get("change_since_previous")
    change = change if isinstance(change, dict) else {}

    technical = facts.get("technical")
    technical = technical if isinstance(technical, dict) else {}
    confirmation_rules = technical.get("confirmation") or facts.get("confirmation")
    invalidation_rules = technical.get("invalidation") or facts.get("invalidation")
    confirmation = _rule_text(confirmation_rules)
    invalidation = _rule_text(invalidation_rules)
    risk_note = normalized_risk_note

    if content_type == "what_changed":
        headline = str(change.get("headline") or "").strip()
        changes = change.get("changes")
        if headline:
            draft = f"{token}: {headline}."
        elif isinstance(changes, list) and changes:
            item = changes[0] if isinstance(changes[0], dict) else {}
            label = str(item.get("label") or "Market evidence")
            previous = str(item.get("previous") or "")
            current = str(item.get("current") or "")
            draft = f"{token}: {label} changed from {previous} to {current}. DexSato remains {decision} with {confidence} confidence."
        else:
            draft = f"{token}: No material previous-scan comparison is available. Current DexSato state is {decision} with {confidence} confidence."

    elif content_type == "trader_brief":
        next_action = str(brief.get("next_action") or "").strip()
        summary = str(brief.get("summary") or "").strip()
        core = next_action or summary
        draft = f"{token}: {decision}, {confidence} confidence."
        if bias:
            draft += f" 4H bias is {bias}."
        if core:
            draft += f" {core}"

    elif content_type == "technical_update":
        parts = [f"{token}: {decision}, {confidence} confidence."]
        if bias:
            parts.append(f"4H bias is {bias}.")
        if volume:
            parts.append(f"Relative volume is {volume}.")
        if rsi:
            parts.append(f"RSI is {rsi}.")
        draft = " ".join(parts)

    elif content_type == "risk_focus":
        draft = f"{token}: {decision}, {confidence} confidence."
        if bias:
            draft += f" 4H bias is {bias}."
        invalidation_rule = _first_rule(invalidation_rules)
        if invalidation_rule:
            status = str(invalidation_rule.get("status") or "").replace("_", " ").strip()
            actual = _as_complete_sentence(invalidation_rule.get("actual"))
            requirement = _as_complete_sentence(invalidation_rule.get("requirement"))
            if status:
                draft += f" Invalidation is {status}."
            if actual:
                draft += f" {actual}"
            if requirement and len(draft) + len(requirement) + 1 <= 270:
                draft += f" {requirement}"
        elif invalidation:
            draft += f" Invalidation: {_as_complete_sentence(invalidation)}"
        elif risk_note:
            draft += f" Risk: {_as_complete_sentence(risk_note)}"

    elif content_type == "fundamental_context":
        context = facts.get("fundamental_context")
        context = context if isinstance(context, dict) else {}
        headline = str(context.get("headline") or "").strip()
        summary = str(context.get("summary") or "").strip()
        if headline or summary:
            draft = f"{token}: {_as_complete_sentence(summary or headline)}"
        else:
            draft = f"{token}: No verified fundamental context is available in the current snapshot. DexSato remains {decision} with {confidence} confidence."

    elif content_type == "catalyst_update":
        catalysts = facts.get("market_catalysts")
        catalysts = catalysts if isinstance(catalysts, dict) else {}
        values = catalysts.get("catalysts")
        first = values[0] if isinstance(values, list) and values and isinstance(values[0], dict) else {}
        title = str(first.get("title") or "").strip()
        source = str(first.get("source") or "").strip()
        if title:
            draft = f"{token}: Verified catalyst context - {title}"
            if source:
                draft += f" ({source})."
            else:
                draft += "."
        else:
            draft = f"{token}: No verified recent catalyst is available in the current snapshot. DexSato remains {decision} with {confidence} confidence."

    else:
        draft = f"{token}: {decision}, {confidence} confidence."
        if bias:
            draft += f" 4H bias is {bias}."
        if volume:
            draft += f" Relative volume is {volume}."
        if rsi:
            draft += f" RSI is {rsi}."
        if confirmation and len(draft) + len(confirmation) + 16 <= 260:
            draft += f" Confirmation: {confirmation}."
        elif decision_summary and len(draft) + len(decision_summary) + 2 <= 260:
            draft += f" {decision_summary.rstrip('.')}."

    # Style-specific deterministic phrasing remains factual.
    if style == "educational" and len(draft) < 220:
        draft += " These are snapshot facts, not a new signal."
    elif style == "concise":
        # Keep the first two complete sentences where possible.
        short = _safe_sentence_limit(draft, 190)
        if short:
            draft = short

    # Remove any accidental Python-container representation before output.
    draft = draft.replace("False", "false").replace("True", "true")
    safe = _safe_sentence_limit(draft, 270)
    if safe and len(safe) <= 280:
        return safe

    # Last resort is deliberately short, factual and complete.
    final = f"{token}: DexSato is {decision} with {confidence} confidence."
    if bias and len(final) + len(bias) + 14 <= 270:
        final += f" 4H bias is {bias}."
    return final[:280]


def _extract_response_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    output = payload.get("output")
    if not isinstance(output, list):
        return ""
    chunks: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    return "\n".join(chunks).strip()



def _looks_complete(value: str) -> bool:
    cleaned = str(value or "").strip()
    if not cleaned:
        return False
    if cleaned.endswith(("≥", "≤", ">", "<", "=", ":", "-", "→", "/", "(", ",")):
        return False
    # Catch obvious abbreviation-style truncation such as "neutral/f."
    if re.search(r"/[A-Za-z]?\.$", cleaned):
        return False
    return cleaned[-1] in ".!?"


def _compress_ai_draft(draft: str, facts: dict[str, object], target: int) -> str:
    """Ask AI to rewrite, never mechanically truncate."""
    market_identity = _market_identity(facts)
    prompt = f"""
Rewrite the X post below so it is a COMPLETE post and at most {min(target, 260)} characters.

Use ONLY facts already present in the post and DEXSATO_FACTS.
Do not add, alter or infer any fact or number.
Begin with the exact market identity "{market_identity}" followed by a colon.
Never cut a rule, threshold, number or sentence.
If a confirmation/invalidation rule cannot fit completely, omit that rule.
End with a complete sentence.
Output ONLY the rewritten post.

POST:
{draft}

DEXSATO_FACTS:
{json.dumps(facts, ensure_ascii=False, separators=(',', ':'))}
""".strip()

    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={
            "Authorization": f"Bearer {_env('OPENAI_API_KEY')}",
            "Content-Type": "application/json",
        },
        json={
            "model": ai_model(),
            "input": prompt,
            "text": {"verbosity": "low"},
            "max_output_tokens": 180,
        },
        timeout=35,
    )
    response.raise_for_status()
    return _extract_response_text(response.json()).strip()


def _classify_ai_error(error: Exception) -> str:
    """Return a concise diagnostic category without leaking secrets."""
    if isinstance(error, requests.Timeout):
        return "AI_TIMEOUT"
    if isinstance(error, requests.HTTPError):
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
        if status == 429:
            return "AI_RATE_LIMIT"
        if status in {400, 404}:
            return "AI_MODEL_OR_REQUEST_ERROR"
        if status in {401, 403}:
            return "AI_AUTH_ERROR"
        if status and status >= 500:
            return "AI_PROVIDER_ERROR"
        return f"AI_HTTP_{status}" if status else "AI_HTTP_ERROR"
    if isinstance(error, requests.RequestException):
        return "AI_NETWORK_ERROR"
    if isinstance(error, RuntimeError):
        return "AI_EMPTY_OR_INVALID_OUTPUT"
    return "AI_ERROR"

def generate_x_draft(
    facts: dict[str, object],
    *,
    content_type: str = "current_update",
    style: str = "trader",
    length: str = "medium",
    writing_style: str | None = None,
    **_: object,
) -> dict[str, object]:
    """Stable writer router: every supported UI combination returns a draft."""
    resolved_type = _resolve_alias(content_type, CONTENT_TYPE_ALIASES, "current_update")
    resolved_style = _resolve_alias(
        writing_style if writing_style is not None else style,
        STYLE_ALIASES,
        "trader",
    )
    resolved_length = _resolve_alias(length, LENGTH_ALIASES, "medium")

    targets = {"short": 160, "medium": 225, "full": 268}
    target = targets[resolved_length]
    market_identity = _market_identity(facts)

    if not ai_enabled():
        return {
            "draft": _fallback_draft(facts, resolved_type, resolved_style),
            "source": "fallback",
            "status": "FALLBACK_GENERATED",
            "diagnostic": None,
            "content_type": resolved_type,
            "style": resolved_style,
            "model": None,
        }

    strategies = {
        "current_update": (
            "Lead with Decision + Confidence and 4H bias. Use 1-2 strongest concrete "
            "technical facts, then the most specific supplied condition that matters."
        ),
        "what_changed": (
            "Lead with material previous-vs-current scan change. Use exact supplied "
            "previous/current values. If no material comparison exists, clearly say so."
        ),
        "trader_brief": (
            "Write a disciplined trader desk brief: current state, strongest evidence, "
            "what is still needed, then invalidation if it fits."
        ),
        "technical_update": (
            "Prioritize supplied 4H RSI, relative volume, EMA distance, market structure "
            "and exact rule states. Do not turn indicators into a new signal."
        ),
        "risk_focus": (
            "Lead with current DexSato state, then report the supplied invalidation status, "
            "actual state and requirement exactly. Invalidation is authoritative and must "
            "appear before general risk commentary, including when it is NOT APPLICABLE."
        ),
        "fundamental_context": (
            "Summarize only verified fundamental context in the supplied snapshot. "
            "State clearly that context is not proof of price causality."
        ),
        "catalyst_update": (
            "Summarize only supplied verified catalyst information. Do not infer sentiment "
            "or claim the catalyst caused price action."
        ),
    }
    styles = {
        "trader": "Natural trader language: direct, observant and concise; no signal-room hype.",
        "professional": "Professional market-intelligence language: restrained, factual and polished.",
        "educational": "Accessible trader language that briefly explains why the supplied evidence matters.",
        "concise": "Very compact trader desk-note style; concrete facts before commentary.",
    }
    variation = random.choice([
        "Lead with the strongest tension in the supplied evidence.",
        "Lead with the most decision-relevant concrete fact after the DexSato state.",
        "Use a compact desk-note rhythm with one clear contrast.",
        "Lead with what a disciplined trader would notice first from the supplied facts.",
    ])

    prompt = f"""
You are DexSato's X writing layer, not its market-analysis engine.

CONTENT TYPE: {resolved_type}
STRATEGY: {strategies[resolved_type]}
STYLE: {styles[resolved_style]}
MARKET IDENTITY: {market_identity}
TARGET: {target} characters. Absolute maximum 280.
VARIATION: {variation}

GROUNDING RULES:
- Use ONLY DEXSATO_FACTS.
- Begin with the exact MARKET IDENTITY followed by a colon. Do not shorten it to the token.
- Decision, Confidence, technical bias and rule states are authoritative.
- Never invent or alter price levels, targets, support/resistance, indicators, events,
  catalysts, causes, probabilities, thresholds or numeric values.
- Never add BUY, SELL, LONG or SHORT unless explicitly present in DEXSATO_FACTS.
- Do not guarantee or predict outcomes.
- Prefer 2-4 decision-relevant facts instead of dumping every field.
- Use exact numbers when supplied and relevant.
- Generic filler is forbidden when a specific supplied fact is available.
- Do not merely say "wait for confirmation" if an exact confirmation rule is supplied.
- Verified fundamental/catalyst context is context, not cause.
- No hashtags or emojis unless supplied.
- End with a COMPLETE sentence.
- Never end on a partial word, slash abbreviation, operator, threshold symbol or unfinished rule.
- If a complete rule cannot fit, omit it.
- Output ONLY the final X post.

DEXSATO_FACTS:
{json.dumps(facts, ensure_ascii=False, separators=(',', ':'))}
""".strip()

    try:
        draft = ""
        for attempt in range(2):
            retry_instruction = (
                "\n\nThe previous response was empty. Return one complete X post now."
                if attempt
                else ""
            )
            response = requests.post(
                OPENAI_RESPONSES_URL,
                headers={
                    "Authorization": f"Bearer {_env('OPENAI_API_KEY')}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": ai_model(),
                    "input": prompt + retry_instruction,
                    "text": {"verbosity": "low"},
                    "max_output_tokens": 220,
                },
                timeout=35,
            )
            response.raise_for_status()
            draft = _extract_response_text(response.json()).strip()
            if draft:
                break

        status = "AI_GENERATED"
        if not draft:
            raise RuntimeError("AI returned an empty draft.")

        identity_missing = (
            market_identity != "MARKET"
            and not draft.upper().startswith(f"{market_identity}:")
        )
        if len(draft) > 280 or not _looks_complete(draft) or identity_missing:
            compressed = _compress_ai_draft(draft, facts, target)
            if compressed and len(compressed) <= 280 and _looks_complete(compressed):
                draft = compressed
                status = "AI_REWRITTEN"
            else:
                safe = _safe_sentence_limit(draft, min(280, target + 30))
                if safe:
                    draft = safe
                    status = "AI_REWRITTEN"
                else:
                    draft = _fallback_draft(facts, resolved_type, resolved_style)
                    status = "FALLBACK_GENERATED"

        return {
            "draft": draft,
            "source": "ai" if status.startswith("AI_") else "fallback",
            "status": status,
            "diagnostic": None,
            "content_type": resolved_type,
            "style": resolved_style,
            "model": ai_model(),
        }

    except (requests.RequestException, RuntimeError, ValueError) as error:
        # Stability rule: generation must never leave the editor blank.
        diagnostic = _classify_ai_error(error)
        return {
            "draft": _fallback_draft(facts, resolved_type, resolved_style),
            "source": "fallback",
            "status": "AI_ERROR_FALLBACK",
            "diagnostic": diagnostic,
            "content_type": resolved_type,
            "style": resolved_style,
            "model": ai_model(),
        }




