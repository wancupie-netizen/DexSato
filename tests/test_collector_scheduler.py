import asyncio
from pathlib import Path
from unittest.mock import patch

from application.collector_scheduler import (
    COLLECTOR_SCRIPT,
    PROVIDER_TIMEOUT_SECONDS,
    CollectorConfiguration,
    CollectorScheduler,
    validate_collector_configuration,
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
