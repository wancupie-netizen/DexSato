"""Focused OOM-02 tests; no providers or full app startup required."""
import asyncio
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('oom02_security', ROOT / 'application/production_security.py')
security = importlib.util.module_from_spec(spec)
spec.loader.exec_module(security)

VIEWS = ('trending', 'top-traded', 'organic-flow', 'recent', 'solana-universe')
ENDPOINTS = ('candles', 'transactions', 'wallet-balance', 'jupiter-quote', 'jupiter-order', 'jupiter-execute')

@pytest.mark.parametrize('view', VIEWS)
def test_market_routes(view):
    assert security._safe_route(f'/market/{view}/PRIVATE_MINT') == f'/market/{view}/:token'
    for endpoint in ENDPOINTS:
        assert security._safe_route(f'/api/market/{view}/PRIVATE_MINT/{endpoint}') == f'/api/market/{view}/:token/{endpoint}'

@pytest.mark.parametrize('path', [
    '/api/market/alien/PRIVATE/candles', '/api/market/trending/PRIVATE/SECRET',
    '/api/discovery/solana/PRIVATE/SECRET', '/api/discovery/solana/PRIVATE/candles/SECRET',
    '/api/market/trending/PRIVATE/candles/SECRET', '/unknown/PRIVATE',
])
def test_unknown_suffixes_are_private(path):
    assert security._safe_route(path) == 'unclassified'


def test_discovery_and_legacy_routes():
    assert security._safe_route('/api/discovery/solana/engine') == '/api/discovery/solana/engine'
    assert security._safe_route('/api/discovery/solana/PRIVATE/candles') == '/api/discovery/solana/:token/candles'
    assert security._safe_route('/api/markets/PRIVATE/quote') == '/api/markets/:token/quote'
    assert security._safe_route('/market/PRIVATE') == '/market/:token'
    assert security._safe_route('/health/live') == '/health/live'


def test_rss_failure_is_null():
    with patch('builtins.open', side_effect=OSError):
        assert security.process_rss_mb() is None
    from unittest.mock import mock_open
    with patch('builtins.open', mock_open(read_data='100 3')), patch.object(security.os, 'sysconf', return_value=4096, create=True):
        assert security.process_rss_mb() == round(3 * 4096 / 1048576, 3)
    with patch('builtins.open', mock_open(read_data='invalid')):
        assert security.process_rss_mb() is None


def scope():
    return {'type': 'http', 'method': 'GET', 'path': '/api/market/solana-universe/PRIVATE/transactions',
            'query_string': b'wallet=SECRET', 'app': SimpleNamespace(state=SimpleNamespace(collector_scheduler=SimpleNamespace(collector_active=True)))}

async def send(message):
    pass

@pytest.mark.parametrize('error', [None, RuntimeError('SECRET'), asyncio.CancelledError()])
def test_completion_exception_cancellation_cleanup(error):
    async def app(scope, receive, send):
        if error is not None:
            raise error
        await send({'type': 'http.response.start', 'status': 503})
        await send({'type': 'http.response.body', 'body': b'SECRET'})
    middleware = security.ProductionLoggingMiddleware(app)
    events = []
    middleware._emit = lambda level, payload: events.append(payload)
    with patch.object(security, 'process_rss_mb', side_effect=[10.0, 12.0]):
        if error is None:
            asyncio.run(middleware(scope(), None, send))
        else:
            with pytest.raises(type(error)):
                asyncio.run(middleware(scope(), None, send))
    assert middleware._active_requests == 0
    assert len(events) == 1
    event = events[0]
    assert event['active_requests_start'] == 1
    assert event['active_requests_end'] == 0
    assert event['rss_mb_delta'] == 2.0
    assert event['collector_active_start'] is True
    assert event['collector_active_end'] is True
    assert 'SECRET' not in str(event) and 'PRIVATE' not in str(event)


def test_concurrent_request_count():
    async def run():
        release = asyncio.Event()
        entered = asyncio.Event()
        count = 0
        async def app(scope, receive, send):
            nonlocal count
            count += 1
            if count == 2:
                entered.set()
            await release.wait()
            await send({'type': 'http.response.start', 'status': 200})
        middleware = security.ProductionLoggingMiddleware(app)
        events = []
        middleware._emit = lambda level, payload: events.append(payload)
        tasks = [asyncio.create_task(middleware(scope(), None, send)) for _ in range(2)]
        await entered.wait()
        assert middleware._active_requests == 2
        release.set()
        await asyncio.gather(*tasks)
        assert sorted(e['active_requests_start'] for e in events) == [1, 2]
        assert sorted(e['active_requests_end'] for e in events) == [0, 1]
        assert middleware._active_requests == 0
    asyncio.run(run())


def test_non_http_passthrough():
    async def app(scope, receive, send):
        assert scope['type'] == 'lifespan'
    middleware = security.ProductionLoggingMiddleware(app)
    middleware._emit = lambda *args: pytest.fail('non HTTP must not log')
    asyncio.run(middleware({'type': 'lifespan'}, None, send))
    assert middleware._active_requests == 0


def test_collector_activity_property():
    # Isolate this property from scheduler imports; full scheduler regression runs in repository.
    tree = ast.parse((ROOT / 'application/collector_scheduler.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CollectorScheduler')
    prop = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'collector_active')
    module = ast.Module(body=[ast.ClassDef(name='Probe', bases=[], keywords=[], body=[prop], decorator_list=[])], type_ignores=[])
    namespace = {}
    exec(compile(ast.fix_missing_locations(module), '<collector-property>', 'exec'), namespace)
    probe = namespace['Probe']()
    for process, expected in [(None, False), (SimpleNamespace(returncode=None), True), (SimpleNamespace(returncode=0), False)]:
        probe._active_process = process
        assert probe.collector_active is expected


def test_missing_rss_and_collector_do_not_block_response():
    async def app(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200})
    middleware = security.ProductionLoggingMiddleware(app)
    events = []
    middleware._emit = lambda level, payload: events.append(payload)
    with patch.object(security, 'process_rss_mb', return_value=None):
        asyncio.run(middleware({'type': 'http', 'path': '/', 'method': 'GET'}, None, send))
    assert events[0]['rss_mb_delta'] is None
    assert events[0]['collector_active_start'] is None
    assert events[0]['status'] == 200


def test_exception_after_response_start_preserves_exception_status():
    async def app(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200})
        raise RuntimeError('private detail')
    middleware = security.ProductionLoggingMiddleware(app)
    events = []
    middleware._emit = lambda level, payload: events.append(payload)
    with pytest.raises(RuntimeError):
        asyncio.run(middleware(scope(), None, send))
    assert events[0]['status'] == 500
    assert events[0]['event'] == 'http_exception'
    assert middleware._active_requests == 0
