import asyncio
import json
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from application.collector_scheduler import (
    COLLECTOR_SCRIPT,
    PROVIDER_TIMEOUT_SECONDS,
    CollectorConfiguration,
    CollectorScheduler,
    validate_collector_configuration,
)
from research.continuous_discovery_runtime import (
    BIRDEYE_QUOTA_COOLDOWN_SECONDS,
    _birdeye_quota_retry_at,
    _http_error_message,
    experiment_status,
    initial_state,
    main as run_continuous_discovery,
)


class FakeProcess:
    def __init__(self, return_code=None):
        self.returncode = return_code
        self.terminated = False
        self.killed = False
        self._finished = asyncio.Event()
        if return_code is not None:
            self._finished.set()

    async def wait(self):
        await self._finished.wait()
        return self.returncode

    def finish(self, return_code=0):
        self.returncode = return_code
        self._finished.set()

    def terminate(self):
        self.terminated = True
        self.finish(-15)

    def kill(self):
        self.killed = True
        self.finish(-9)


class ProcessFactory:
    def __init__(self, *processes):
        self.processes = list(processes)
        self.calls = []

    async def __call__(self, *command, **kwargs):
        self.calls.append((command, kwargs))
        return self.processes.pop(0)


def _configuration(tmp_path: Path, **overrides) -> CollectorConfiguration:
    values = {
        "enabled": True,
        "interval_seconds": 900,
        "timeout_seconds": 600,
        "limit": 20,
        "output_directory": tmp_path,
    }
    values.update(overrides)
    return CollectorConfiguration(**values)


def test_collector_configuration_is_disabled_by_default(tmp_path):
    with patch.dict(
        "os.environ", {"DEXSATO_DISCOVERY_STORAGE_DIR": str(tmp_path)}, clear=True
    ):
        configuration = CollectorConfiguration.from_environment()
    assert configuration.enabled is False
    assert configuration.interval_seconds == 900
    assert configuration.timeout_seconds == 600
    assert configuration.limit == 20


def test_collector_configuration_rejects_timeout_at_or_above_interval(tmp_path):
    environment = {
        "DEXSATO_DISCOVERY_STORAGE_DIR": str(tmp_path),
        "DEXSATO_COLLECTOR_INTERVAL_SECONDS": "600",
        "DEXSATO_COLLECTOR_TIMEOUT_SECONDS": "600",
    }
    with patch.dict("os.environ", environment, clear=True):
        try:
            validate_collector_configuration()
        except RuntimeError as error:
            assert "must be less than" in str(error)
        else:
            raise AssertionError("Expected unsafe collector timing to fail")


def test_disabled_collector_does_not_start_scheduler(tmp_path):
    async def scenario():
        scheduler = CollectorScheduler(_configuration(tmp_path, enabled=False))
        await scheduler.start()
        assert scheduler.running is False
        await scheduler.stop()

    asyncio.run(scenario())


def test_scheduler_invokes_expected_one_shot_command(tmp_path):
    async def scenario():
        process = FakeProcess(0)
        factory = ProcessFactory(process)
        scheduler = CollectorScheduler(
            _configuration(tmp_path), process_factory=factory
        )
        assert await scheduler.run_cycle() == "success"
        command, kwargs = factory.calls[0]
        assert command == (
            __import__("sys").executable,
            str(COLLECTOR_SCRIPT),
            "--output-dir",
            str(tmp_path),
            "--limit",
            "20",
            "--timeout-seconds",
            str(PROVIDER_TIMEOUT_SECONDS),
        )
        assert kwargs["stdout"] == asyncio.subprocess.DEVNULL
        assert kwargs["stderr"] == asyncio.subprocess.DEVNULL

    asyncio.run(scenario())


def test_second_cycle_cannot_overlap_first(tmp_path):
    async def scenario():
        process = FakeProcess()
        factory = ProcessFactory(process)
        scheduler = CollectorScheduler(
            _configuration(tmp_path), process_factory=factory
        )
        first = asyncio.create_task(scheduler.run_cycle())
        await asyncio.sleep(0)
        assert await scheduler.run_cycle() == "skipped"
        process.finish(0)
        assert await first == "success"
        assert len(factory.calls) == 1

    asyncio.run(scenario())


def test_collector_timeout_terminates_process_without_raising(tmp_path):
    async def scenario():
        process = FakeProcess()
        factory = ProcessFactory(process)
        scheduler = CollectorScheduler(
            _configuration(tmp_path, timeout_seconds=0.01), process_factory=factory
        )
        assert await scheduler.run_cycle() == "timeout"
        assert process.terminated is True

    asyncio.run(scenario())


def test_nonzero_cycle_does_not_prevent_next_cycle(tmp_path):
    async def scenario():
        factory = ProcessFactory(FakeProcess(1), FakeProcess(0))
        scheduler = CollectorScheduler(
            _configuration(tmp_path), process_factory=factory
        )
        assert await scheduler.run_cycle() == "failed"
        assert await scheduler.run_cycle() == "success"
        assert len(factory.calls) == 2

    asyncio.run(scenario())


def test_shutdown_terminates_active_collector_and_stops_scheduler(tmp_path):
    async def scenario():
        process = FakeProcess()
        factory = ProcessFactory(process)
        scheduler = CollectorScheduler(
            _configuration(tmp_path, interval_seconds=1), process_factory=factory
        )
        await scheduler.start()
        await asyncio.sleep(0)
        assert scheduler.running is True
        await scheduler.stop()
        assert process.terminated is True
        assert scheduler.running is False

    asyncio.run(scenario())


def test_shutdown_during_process_creation_stops_new_process(tmp_path):
    async def scenario():
        process = FakeProcess()
        release = asyncio.Event()
        factory_called = asyncio.Event()

        async def delayed_factory(*_command, **_kwargs):
            factory_called.set()
            await release.wait()
            return process

        scheduler = CollectorScheduler(
            _configuration(tmp_path), process_factory=delayed_factory
        )
        await scheduler.start()
        await factory_called.wait()
        stopping = asyncio.create_task(scheduler.stop())
        await asyncio.sleep(0)
        release.set()
        await stopping
        assert process.terminated is True
        assert scheduler.running is False

    asyncio.run(scenario())


def test_collector_sigterm_path_raises_system_exit_for_lock_cleanup():
    from research.continuous_discovery_runtime import _graceful_termination

    try:
        _graceful_termination(15, None)
    except SystemExit as error:
        assert error.code == 143
    else:
        raise AssertionError("Expected SIGTERM handler to stop through finally")


def test_birdeye_quota_message_is_read_from_bounded_http_error_body():
    error = HTTPError(
        "https://public-api.birdeye.so/defi/v2/tokens/new_listing",
        400,
        "Bad Request",
        {},
        BytesIO(b'{"success":false,"message":"Compute units usage limit exceeded"}'),
    )
    assert _http_error_message(error) == "Compute units usage limit exceeded"


def test_birdeye_quota_cooldown_is_persisted_and_expires():
    current = datetime(2026, 9, 15, tzinfo=timezone.utc)
    retry_at = current + timedelta(seconds=BIRDEYE_QUOTA_COOLDOWN_SECONDS)
    state = {"birdeye_quota_retry_at": retry_at.isoformat()}
    assert _birdeye_quota_retry_at(state, current) == retry_at
    assert _birdeye_quota_retry_at(state, retry_at) is None


def test_quota_warning_is_degraded_without_becoming_attention():
    current = datetime(2026, 9, 15, tzinfo=timezone.utc)
    state = initial_state(current)
    state["last_warnings"] = ["Birdeye compute-unit quota exhausted"]
    assert experiment_status(state, current) == "DEGRADED"
    state["last_errors"] = ["DexScreener profiles HTTPError"]
    assert experiment_status(state, current) == "ATTENTION"


def test_scheduler_reports_persisted_degraded_status_in_success_log(tmp_path, caplog):
    async def scenario():
        (tmp_path / "status.json").write_text(
            json.dumps({"collector_status": "DEGRADED"}), encoding="utf-8"
        )
        scheduler = CollectorScheduler(
            _configuration(tmp_path), process_factory=ProcessFactory(FakeProcess(0))
        )
        assert await scheduler.run_cycle() == "success"

    with caplog.at_level("INFO", logger="dexsato.production"):
        asyncio.run(scenario())
    payload = json.loads(caplog.records[-1].message)
    assert payload["event"] == "collector_cycle_succeeded"
    assert payload["return_code"] == 0
    assert payload["collector_status"] == "DEGRADED"


def test_quota_exhaustion_degrades_cycle_and_cooldown_skips_next_request(tmp_path):
    def quota_error():
        return HTTPError(
            "https://public-api.birdeye.so/defi/v2/tokens/new_listing",
            400,
            "Bad Request",
            {},
            BytesIO(b'{"success":false,"message":"Compute units usage limit exceeded"}'),
        )

    arguments = [
        "continuous_discovery_runtime.py",
        "--output-dir",
        str(tmp_path),
    ]
    profile_run = {
        "provider": "dexscreener-profiles",
        "latency_ms": 1.0,
        "received": 0,
    }
    with (
        patch.dict("os.environ", {"BIRDEYE_API_KEY": "configured"}, clear=True),
        patch("sys.argv", arguments),
        patch(
            "research.continuous_discovery_runtime.collect_birdeye",
            side_effect=quota_error(),
        ) as birdeye,
        patch(
            "research.continuous_discovery_runtime.collect_dex_profiles",
            return_value=([], profile_run),
        ),
        patch("research.continuous_discovery_runtime.refresh_solana_discovery_archive"),
    ):
        assert run_continuous_discovery() == 0
        assert run_continuous_discovery() == 0

    assert birdeye.call_count == 1
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert state["failed_runs"] == 0
    assert state["successful_runs"] == 0
    assert state["degraded_runs"] == 2
    assert status["collector_status"] == "DEGRADED"
    assert status["last_run"]["errors"] == []
    assert status["last_run"]["provider_runs"][0]["request_attempted"] is False
