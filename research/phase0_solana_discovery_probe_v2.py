#!/usr/bin/env python3
"""DexSato Phase 0: read-only Solana discovery source probe.

This script is deliberately isolated from the production engine, database,
dashboard, scheduler, and Telegram notifier.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BIRDEYE_URL = "https://public-api.birdeye.so/defi/v2/tokens/new_listing"
DEX_PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
DEX_TOKENS_URL = "https://api.dexscreener.com/tokens/v1/solana/{}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_json(url: str, headers: dict[str, str], timeout: float) -> tuple[Any, float]:
    started = time.perf_counter()
    request = Request(url, headers={"User-Agent": "DexSato-Phase0-Probe/1.0", **headers})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload, round((time.perf_counter() - started) * 1000, 2)


def extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    data = payload.get("data", payload)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("items", "tokens", "list"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def token_address(item: dict[str, Any]) -> str | None:
    for key in ("address", "tokenAddress", "token_address", "baseTokenAddress"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    token = item.get("token")
    if isinstance(token, dict):
        return token_address(token)
    return None


def collect_birdeye(api_key: str, limit: int, include_meme: bool, timeout: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = {
        "limit": limit,
        "meme_platform_enabled": str(include_meme).lower(),
    }
    payload, latency = request_json(
        f"{BIRDEYE_URL}?{urlencode(params)}",
        {"X-API-KEY": api_key, "x-chain": "solana", "accept": "application/json"},
        timeout,
    )
    candidates = []
    for item in extract_items(payload):
        address = token_address(item)
        if address:
            candidates.append({
                "provider": "birdeye",
                "chain": "solana",
                "token_address": address,
                "pair_address": None,
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "listed_at": item.get("liquidityAddedAt") or item.get("listed_at") or item.get("createdAt"),
            })
    return candidates, {"provider": "birdeye", "latency_ms": latency, "received": len(candidates)}


def collect_dex_profiles(timeout: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload, latency = request_json(DEX_PROFILES_URL, {"accept": "application/json"}, timeout)
    candidates = []
    for item in extract_items(payload):
        if str(item.get("chainId", "")).lower() != "solana":
            continue
        address = token_address(item)
        if address:
            candidates.append({
                "provider": "dexscreener-profiles",
                "chain": "solana",
                "token_address": address,
                "pair_address": None,
                "symbol": None,
                "name": None,
                "listed_at": None,
            })
    return candidates, {"provider": "dexscreener-profiles", "latency_ms": latency, "received": len(candidates)}


def enrich(candidates: list[dict[str, Any]], timeout: float) -> dict[str, Any]:
    addresses = list(dict.fromkeys(c["token_address"] for c in candidates))
    resolved = 0
    latency_total = 0.0
    for offset in range(0, len(addresses), 30):
        batch = addresses[offset:offset + 30]
        payload, latency = request_json(DEX_TOKENS_URL.format(",".join(batch)), {"accept": "application/json"}, timeout)
        latency_total += latency
        pairs = extract_items(payload)
        selected: dict[str, dict[str, Any]] = {}
        for pair in pairs:
            base = pair.get("baseToken") or {}
            address = token_address(base)
            if not address or address not in batch:
                continue
            current = selected.get(address)
            if current is None or (pair.get("pairCreatedAt") or 0) > (current.get("pairCreatedAt") or 0):
                selected[address] = pair
        for candidate in candidates:
            pair = selected.get(candidate["token_address"])
            if pair and not candidate.get("pair_address"):
                candidate["pair_address"] = pair.get("pairAddress")
                base = pair.get("baseToken") or {}
                candidate["symbol"] = candidate.get("symbol") or base.get("symbol")
                candidate["name"] = candidate.get("name") or base.get("name")
                candidate["listed_at"] = candidate.get("listed_at") or pair.get("pairCreatedAt")
                if candidate["pair_address"]:
                    resolved += 1
    return {"provider": "dexscreener-enrichment", "latency_ms": round(latency_total, 2), "resolved": resolved}


def write_outputs(output_dir: Path, candidates: list[dict[str, Any]], runs: list[dict[str, Any]], errors: list[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in candidates:
        unique[(candidate["provider"], candidate["token_address"])] = candidate
    records = list(unique.values())
    ready = sum(bool(record.get("pair_address")) for record in records)
    summary = {
        "phase": "Phase 0 — Data-source proof only",
        "status": "MEASUREMENT_COMPLETE" if not errors else "MEASUREMENT_WITH_ERRORS",
        "generated_at": utc_now(),
        "unique_candidates": len(records),
        "pair_identity_ready": ready,
        "pair_identity_ready_percent": round(ready * 100 / len(records), 2) if records else 0.0,
        "provider_runs": runs,
        "errors": errors,
        "phase_1_authorized": False,
    }
    with (output_dir / "candidates.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    (output_dir / "runs.jsonl").write_text(
        "".join(json.dumps(run, ensure_ascii=False) + "\n" for run in runs), encoding="utf-8"
    )
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    report = [
        "# DexSato Solana Discovery — Phase 0 Measurement",
        "",
        f"- Status: `{summary['status']}`",
        f"- Generated: `{summary['generated_at']}`",
        f"- Unique candidates: **{len(records)}**",
        f"- Pair identity ready: **{ready}/{len(records)} ({summary['pair_identity_ready_percent']}%)**",
        f"- Provider errors: **{len(errors)}**",
        "",
        "This generated report does not authorize Phase 1.",
    ]
    (output_dir / "measurement.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure candidate coverage from Solana discovery sources.")
    parser.add_argument("--provider", choices=("birdeye", "dexscreener-profiles", "both"), default="both")
    parser.add_argument("--limit", type=int, choices=range(1, 21), default=20)
    parser.add_argument("--include-meme-platforms", action="store_true")
    parser.add_argument("--enrich-dexscreener", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--output-dir", default="output/research/solana-discovery-phase0")
    args = parser.parse_args()

    candidates: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    errors: list[str] = []
    if args.provider in ("birdeye", "both"):
        try:
            key = os.getenv("BIRDEYE_API_KEY", "").strip()
            if not key:
                raise RuntimeError("BIRDEYE_API_KEY is not set in this PowerShell session")
            found, run = collect_birdeye(key, args.limit, args.include_meme_platforms, args.timeout_seconds)
            candidates.extend(found)
            runs.append(run)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            errors.append(f"birdeye: HTTP {exc.code}: {body}")
        except (URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            errors.append(f"birdeye: {type(exc).__name__}: {exc}")

    if args.provider in ("dexscreener-profiles", "both"):
        try:
            found, run = collect_dex_profiles(args.timeout_seconds)
            candidates.extend(found)
            runs.append(run)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            errors.append(f"dexscreener-profiles: HTTP {exc.code}: {body}")
        except (URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            errors.append(f"dexscreener-profiles: {type(exc).__name__}: {exc}")

    if args.enrich_dexscreener and candidates:
        try:
            runs.append(enrich(candidates, args.timeout_seconds))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            errors.append(f"dexscreener-enrichment: HTTP {exc.code}: {body}")
        except (URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            errors.append(f"dexscreener-enrichment: {type(exc).__name__}: {exc}")

    output_dir = Path(args.output_dir)
    write_outputs(output_dir, candidates, runs, errors)
    print(f"Phase 0 output: {output_dir.resolve()}")
    print(f"Candidates: {len(candidates)} | Errors: {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
