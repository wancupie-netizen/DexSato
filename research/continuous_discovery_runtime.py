#!/usr/bin/env python3
"""DexSato MI v4.1 continuous Solana discovery runtime.

Runs once per invocation. Windows Task Scheduler invokes it every 15
minutes. It resumes the existing Phase 0 state without resetting observations,
and keeps discovery acquisition/pair resolution bounded per cycle.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

try:
    from .phase0_solana_discovery_probe_v2 import (
        collect_birdeye,
        collect_dex_profiles,
        enrich,
    )
except ImportError:
    from phase0_solana_discovery_probe_v2 import (
        collect_birdeye,
        collect_dex_profiles,
        enrich,
    )


UTC = timezone.utc
MYT = timezone(timedelta(hours=8), name="MYT")
INTERVAL_MINUTES = 15
MAX_DAYS = 7
MAX_RUNS = 672
PAIR_RETRY_MINUTES = (0, 15, 30, 60)
DEFAULT_OUTPUT = "output/research/solana-discovery-phase0-seven-day"


def now_utc() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def display_time(value: str | None) -> str:
    parsed = parse_time(value)
    return parsed.astimezone(MYT).strftime("%d %b %Y, %I:%M %p MYT") if parsed else "—"


def read_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "BIRDEYE_API_KEY" and not os.getenv("BIRDEYE_API_KEY"):
            os.environ["BIRDEYE_API_KEY"] = value.strip().strip('"').strip("'")


def initial_state(started_at: datetime) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "phase": "Phase 0 — Data-source proof only",
        "started_at": iso(started_at),
        "ends_at": iso(started_at + timedelta(days=MAX_DAYS)),
        "run_count": 0,
        "successful_runs": 0,
        "failed_runs": 0,
        "birdeye_calls": 0,
        "estimated_birdeye_cu": 0,
        "last_run_at": None,
        "last_success_at": None,
        "last_errors": [],
        "candidates": {},
        "latest_birdeye_addresses": [],
        "latest_dex_profile_addresses": [],
        "phase_1_authorized": False,
            "runtime_mode": "MI v4.1 CONTINUOUS",
    }


def load_state(path: Path, current: datetime) -> dict[str, Any]:
    if not path.exists():
        return initial_state(current)
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def append_jsonl(path: Path, payload: Any) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def candidate_due(candidate: dict[str, Any], current: datetime) -> bool:
    if candidate.get("pair_address"):
        return False
    attempts = int(candidate.get("pair_attempts", 0))
    if attempts >= len(PAIR_RETRY_MINUTES):
        return False
    first_seen = parse_time(candidate.get("first_seen_at"))
    if first_seen is None:
        return True
    return current >= first_seen + timedelta(minutes=PAIR_RETRY_MINUTES[attempts])


def merge_discovery(
    state: dict[str, Any],
    records: list[dict[str, Any]],
    provider: str,
    observed_at: datetime,
    events_path: Path,
) -> int:
    created = 0
    candidates = state["candidates"]
    for record in records:
        address = record["token_address"]
        candidate = candidates.get(address)
        if candidate is None:
            candidate = {
                "token_address": address,
                "symbol": record.get("symbol"),
                "name": record.get("name"),
                "listed_at": record.get("listed_at"),
                "first_seen_at": iso(observed_at),
                "last_seen_at": iso(observed_at),
                "sources": [provider],
                "pair_address": record.get("pair_address"),
                "pair_resolved_at": iso(observed_at) if record.get("pair_address") else None,
                "time_to_pair_minutes": 0.0 if record.get("pair_address") else None,
                "pair_attempts": 0,
            }
            candidates[address] = candidate
            created += 1
            append_jsonl(events_path, {"event": "candidate_discovered", "at": iso(observed_at), **candidate})
        else:
            candidate["last_seen_at"] = iso(observed_at)
            if provider not in candidate["sources"]:
                candidate["sources"].append(provider)
            candidate["symbol"] = candidate.get("symbol") or record.get("symbol")
            candidate["name"] = candidate.get("name") or record.get("name")
            candidate["listed_at"] = candidate.get("listed_at") or record.get("listed_at")
    return created


def resolve_due_pairs(state: dict[str, Any], current: datetime, timeout: float, events_path: Path) -> dict[str, Any]:
    due = [candidate for candidate in state["candidates"].values() if candidate_due(candidate, current)]
    if not due:
        return {"provider": "dexscreener-enrichment", "latency_ms": 0.0, "attempted": 0, "resolved": 0}
    probe_records = [
        {
            "provider": "collector",
            "chain": "solana",
            "token_address": candidate["token_address"],
            "pair_address": None,
            "symbol": candidate.get("symbol"),
            "name": candidate.get("name"),
            "listed_at": candidate.get("listed_at"),
        }
        for candidate in due
    ]
    result = enrich(probe_records, timeout)
    resolved = 0
    for candidate, enriched_record in zip(due, probe_records):
        candidate["pair_attempts"] = int(candidate.get("pair_attempts", 0)) + 1
        if not enriched_record.get("pair_address"):
            continue
        candidate["pair_address"] = enriched_record["pair_address"]
        candidate["symbol"] = candidate.get("symbol") or enriched_record.get("symbol")
        candidate["name"] = candidate.get("name") or enriched_record.get("name")
        candidate["pair_resolved_at"] = iso(current)
        first_seen = parse_time(candidate["first_seen_at"]) or current
        candidate["time_to_pair_minutes"] = round((current - first_seen).total_seconds() / 60, 2)
        resolved += 1
        append_jsonl(
            events_path,
            {
                "event": "pair_resolved",
                "at": iso(current),
                "token_address": candidate["token_address"],
                "pair_address": candidate["pair_address"],
                "time_to_pair_minutes": candidate["time_to_pair_minutes"],
            },
        )
    return {**result, "attempted": len(due), "resolved": resolved}


def metrics(state: dict[str, Any], current: datetime) -> dict[str, Any]:
    candidates = list(state["candidates"].values())
    birdeye = [item for item in candidates if "birdeye" in item["sources"]]
    profiles = [item for item in candidates if "dexscreener-profiles" in item["sources"]]
    overlap = [item for item in candidates if len(set(item["sources"])) > 1]
    resolved = [item for item in birdeye if item.get("pair_address")]
    waiting = [item for item in birdeye if not item.get("pair_address") and int(item.get("pair_attempts", 0)) < 4]
    exhausted = [item for item in birdeye if not item.get("pair_address") and int(item.get("pair_attempts", 0)) >= 4]
    times = [float(item["time_to_pair_minutes"]) for item in resolved if item.get("time_to_pair_minutes") is not None]
    started = parse_time(state["started_at"]) or current
    ends = parse_time(state["ends_at"]) or current
    duration = max((ends - started).total_seconds(), 1)
    progress = min(max((current - started).total_seconds() / duration * 100, 0), 100)
    return {
        "birdeye_unique": len(birdeye),
        "dex_profiles_unique": len(profiles),
        "provider_overlap": len(overlap),
        "pair_resolved": len(resolved),
        "pair_waiting": len(waiting),
        "pair_unresolved_after_retries": len(exhausted),
        "pair_ready_percent": round(len(resolved) * 100 / len(birdeye), 2) if birdeye else 0.0,
        "average_time_to_pair_minutes": round(sum(times) / len(times), 2) if times else None,
        "progress_percent": round(progress, 2),
        "next_expected_run_at": iso(current + timedelta(minutes=INTERVAL_MINUTES)),
    }


def experiment_status(state: dict[str, Any], current: datetime) -> str:
    # MI v4.1: Phase 0 completion is historical; continuous runtime does not
    # reset state and is no longer bounded by ends_at/MAX_RUNS.
    if state["last_errors"]:
        return "ATTENTION"
    return "RUNNING"


def write_latest_run(path: Path, state: dict[str, Any], summary: dict[str, Any]) -> None:
    lines = [
        "DexSato Phase 0 — Latest Run",
        "=" * 44,
        f"Status             : {summary['collector_status']}",
        f"Last run           : {display_time(state['last_run_at'])}",
        f"Next expected      : {display_time(summary['metrics']['next_expected_run_at'])}",
        f"Run count          : {state['run_count']}/{MAX_RUNS}",
        f"Birdeye candidates : {summary['metrics']['birdeye_unique']}",
        f"Pair ready         : {summary['metrics']['pair_resolved']}",
        f"Pair waiting       : {summary['metrics']['pair_waiting']}",
        f"Estimated CU       : {state['estimated_birdeye_cu']}/20160",
        f"Errors             : {len(state['last_errors'])}",
        "Runtime            : MI v4.1 CONTINUOUS",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(path: Path, state: dict[str, Any], summary: dict[str, Any]) -> None:
    data = summary["metrics"]
    candidates = sorted(
        (item for item in state["candidates"].values() if "birdeye" in item["sources"]),
        key=lambda item: item["first_seen_at"],
        reverse=True,
    )[:20]
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(item.get('symbol') or '—')}</td>"
        f"<td><code>{html.escape(item['token_address'][:8])}…{html.escape(item['token_address'][-6:])}</code></td>"
        f"<td>{display_time(item['first_seen_at'])}</td>"
        f"<td>{'READY' if item.get('pair_address') else 'WAITING'}</td>"
        f"<td>{html.escape(str(item.get('time_to_pair_minutes') if item.get('time_to_pair_minutes') is not None else '—'))}</td>"
        "</tr>"
        for item in candidates
    ) or '<tr><td colspan="5">No Birdeye candidates recorded yet.</td></tr>'
    errors = "".join(f"<li>{html.escape(error)}</li>" for error in state["last_errors"]) or "<li>None</li>"
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="60">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DexSato Continuous Discovery Monitor</title>
<style>
:root{{--bg:#f5f8fc;--panel:#ffffff;--line:#d8e2ec;--text:#10243a;--muted:#60758a;--cyan:#087f74;--blue:#1769c2;--amber:#9a6700;--red:#c9364f}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font:15px system-ui,Segoe UI,sans-serif}}
main{{max-width:1180px;margin:auto;padding:28px}} h1{{margin:0 0 6px}} .sub{{color:var(--muted);margin-bottom:24px}}
.badge{{display:inline-block;padding:7px 12px;border:1px solid #9bd8d2;border-radius:999px;background:#e9f8f6;color:var(--cyan);font-weight:700}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:18px 0}}
.card,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 3px 12px rgba(16,36,58,.04)}} .label{{color:var(--muted);font-size:12px;text-transform:uppercase}} .value{{font-size:24px;font-weight:700;margin-top:7px}}
.progress{{height:10px;background:#e5edf5;border-radius:8px;overflow:hidden}} .progress span{{display:block;height:100%;background:linear-gradient(90deg,var(--blue),var(--cyan));width:{data['progress_percent']}%}}
table{{width:100%;border-collapse:collapse}} th,td{{padding:11px;text-align:left;border-bottom:1px solid var(--line)}} th{{color:#425b72;background:#f8fafc}} tbody tr:hover{{background:#f7fafc}} code{{color:#155da5}}
.footer{{text-align:center;color:var(--muted);padding:22px}} @media(max-width:700px){{main{{padding:16px}} table{{font-size:12px}}}}
</style></head><body><main>
<div class="badge">{html.escape(summary['collector_status'])}</div>
<h1>DexSato Solana Discovery</h1><div class="sub">Phase 0 seven-day data-source proof · local monitor only</div>
<div class="panel"><div class="label">Experiment progress — {data['progress_percent']}%</div><div class="progress"><span></span></div>
<p>Started {display_time(state['started_at'])} · Ends {display_time(state['ends_at'])} · Last run {display_time(state['last_run_at'])}</p></div>
<div class="grid">
<div class="card"><div class="label">Runs</div><div class="value">{state['run_count']} / {MAX_RUNS}</div></div>
<div class="card"><div class="label">Estimated Birdeye CU</div><div class="value">{state['estimated_birdeye_cu']} / 20,160</div></div>
<div class="card"><div class="label">Birdeye unique</div><div class="value">{data['birdeye_unique']}</div></div>
<div class="card"><div class="label">Pair ready</div><div class="value">{data['pair_resolved']} ({data['pair_ready_percent']}%)</div></div>
<div class="card"><div class="label">Pair waiting</div><div class="value">{data['pair_waiting']}</div></div>
<div class="card"><div class="label">Average time-to-pair</div><div class="value">{data['average_time_to_pair_minutes'] if data['average_time_to_pair_minutes'] is not None else '—'} min</div></div>
</div>
<div class="panel"><h2>Latest Birdeye candidates</h2><table><thead><tr><th>Token</th><th>Address</th><th>First seen</th><th>Pair</th><th>Minutes</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="panel" style="margin-top:12px"><h2>Last errors</h2><ul>{errors}</ul><p>DexScreener profiles unique: {data['dex_profiles_unique']} · Provider overlap: {data['provider_overlap']} · Unresolved after retries: {data['pair_unresolved_after_retries']}</p></div>
<div class="footer">Phase 1 is not authorized · This page refreshes every 60 seconds · Made for Sya ❤️</div>
</main></body></html>"""
    path.write_text(document, encoding="utf-8")


def acquire_lock(path: Path) -> int | None:
    try:
        return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            if time.time() - path.stat().st_mtime > 30 * 60:
                path.unlink()
                return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileNotFoundError:
            return acquire_lock(path)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one scheduled DexSato MI v4.1 continuous discovery cycle.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT)
    parser.add_argument("--env-file", default=".env.phase0.local")
    parser.add_argument("--limit", type=int, choices=range(1, 21), default=20)
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    output = Path(args.output_dir)
    if not output.is_absolute():
        output = root / output
    env_file = Path(args.env_file)
    if not env_file.is_absolute():
        env_file = root / env_file
    output.mkdir(parents=True, exist_ok=True)
    lock_path = output / "collector.lock"
    lock_fd = acquire_lock(lock_path)
    if lock_fd is None:
        print("Phase 0 collector is already running; this invocation was skipped.")
        return 0

    current = now_utc()
    state_path = output / "state.json"
    events_path = output / "candidate-events.jsonl"
    runs_path = output / "runs.jsonl"
    try:
        read_env_file(env_file)
        state = load_state(state_path, current)

        key = os.getenv("BIRDEYE_API_KEY", "").strip()
        errors: list[str] = []
        provider_runs: list[dict[str, Any]] = []
        new_birdeye = 0
        new_profiles = 0
        pair_run: dict[str, Any] = {"attempted": 0, "resolved": 0, "latency_ms": 0.0}
        state["run_count"] += 1
        state["last_run_at"] = iso(current)

        if not key:
            errors.append(f"BIRDEYE_API_KEY was not found in {env_file.name}")
        else:
            try:
                records, run = collect_birdeye(key, args.limit, True, args.timeout_seconds)
                state["birdeye_calls"] += 1
                state["estimated_birdeye_cu"] = state["birdeye_calls"] * 30
                provider_runs.append(run)
                state["latest_birdeye_addresses"] = [item["token_address"] for item in records]
                new_birdeye = merge_discovery(state, records, "birdeye", current, events_path)
            except HTTPError as exc:
                state["birdeye_calls"] += 1
                state["estimated_birdeye_cu"] = state["birdeye_calls"] * 30
                errors.append(f"Birdeye HTTP {exc.code}")
            except (URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
                errors.append(f"Birdeye {type(exc).__name__}: {exc}")

        try:
            records, run = collect_dex_profiles(args.timeout_seconds)
            provider_runs.append(run)
            state["latest_dex_profile_addresses"] = [item["token_address"] for item in records]
            new_profiles = merge_discovery(state, records, "dexscreener-profiles", current, events_path)
        except (HTTPError, URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            errors.append(f"DexScreener profiles {type(exc).__name__}: {exc}")

        try:
            pair_run = resolve_due_pairs(state, current, args.timeout_seconds, events_path)
            provider_runs.append(pair_run)
        except (HTTPError, URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            errors.append(f"DexScreener enrichment {type(exc).__name__}: {exc}")

        state["last_errors"] = errors
        if errors:
            state["failed_runs"] += 1
        else:
            state["successful_runs"] += 1
            state["last_success_at"] = iso(current)
        run_record = {
            "run_number": state["run_count"],
            "at": iso(current),
            "new_birdeye_candidates": new_birdeye,
            "new_dex_profile_candidates": new_profiles,
            "pair_attempted": pair_run.get("attempted", 0),
            "pair_resolved": pair_run.get("resolved", 0),
            "provider_runs": provider_runs,
            "errors": errors,
        }
        append_jsonl(runs_path, run_record)
        state_metrics = metrics(state, current)
        summary = {
            "collector_status": experiment_status(state, current),
            "generated_at": iso(current),
            "metrics": state_metrics,
            "last_run": run_record,
            "phase_1_authorized": False,
            "runtime_mode": "MI v4.1 CONTINUOUS",
        }
        atomic_json(state_path, state)
        atomic_json(output / "status.json", summary)
        write_latest_run(output / "latest-run.txt", state, summary)
        write_html(output / "status.html", state, summary)
        print(f"MI v4.1 continuous run {state['run_count']}: {summary['collector_status']}")
        print(f"Birdeye unique: {state_metrics['birdeye_unique']} | Pair ready: {state_metrics['pair_resolved']} | Errors: {len(errors)}")
        print(f"Local monitor: {output / 'status.html'}")
        return 1 if errors else 0
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
