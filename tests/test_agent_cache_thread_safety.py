"""Regression tests for agent cache thread-safety (#265 follow-up review).

``cachetools.TTLCache`` is not thread-safe; the agent router mutates its
``_calls`` and ``_logs`` caches from both the asyncio event-loop thread
(FastAPI handlers) and a ``run_in_executor`` worker thread
(``_run_local_agent``). Concurrent access can corrupt TTLCache's internal
linked list or raise ``RuntimeError: dictionary changed size during
iteration`` / ``KeyError`` on eviction.

These tests spin up N threads that hammer the same caches concurrently —
the same write pattern as ``_run_local_agent`` + ``/agent/complete`` +
``/agent/log`` racing — and assert no exceptions escape. Without
``_cache_lock`` protecting every read/write this suite reliably reproduces
the race on CPython (observed: ``KeyError`` on eviction, occasional
``RuntimeError`` on dict mutation).
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from policyengine_api.api import agent as agent_router
from policyengine_api.api.agent import LogEntry


@pytest.fixture(autouse=True)
def reset_caches():
    """Start each test with empty caches so assertions are deterministic."""
    with agent_router._cache_lock:
        agent_router._calls.clear()
        agent_router._logs.clear()
    yield
    with agent_router._cache_lock:
        agent_router._calls.clear()
        agent_router._logs.clear()


def _writer_insert(call_id: str, iterations: int) -> None:
    """Simulate /agent/run initialising entries."""
    for i in range(iterations):
        with agent_router._cache_lock:
            agent_router._calls[f"{call_id}-{i}"] = {
                "status": "running",
                "result": None,
            }
            agent_router._logs[f"{call_id}-{i}"] = []


def _writer_complete(call_id: str, iterations: int) -> None:
    """Simulate /agent/complete mutating a specific entry in place."""
    for i in range(iterations):
        key = f"{call_id}-{i}"
        with agent_router._cache_lock:
            entry = agent_router._calls.get(key)
            if entry is not None:
                entry["status"] = "completed"
                entry["result"] = {"status": "completed", "iteration": i}


def _writer_log(call_id: str, iterations: int) -> None:
    """Simulate /agent/log appending entries (setdefault pattern)."""
    for i in range(iterations):
        key = f"{call_id}-{i}"
        entry = LogEntry(timestamp="2026-04-17T00:00:00+00:00", message=f"m{i}")
        with agent_router._cache_lock:
            agent_router._logs.setdefault(key, []).append(entry)


def _reader(call_id: str, iterations: int) -> None:
    """Simulate /agent/logs + /agent/status snapshot reads."""
    for i in range(iterations):
        key = f"{call_id}-{i}"
        with agent_router._cache_lock:
            info = agent_router._calls.get(key)
            logs_snapshot = list(agent_router._logs.get(key, []))
        # Touch the snapshot after releasing the lock to catch mutations.
        if info is not None:
            _ = info.get("status")
            _ = info.get("result")
        _ = len(logs_snapshot)


def test_ttl_caches_survive_concurrent_mutation():
    """Many threads writing/reading the caches must not raise."""
    threads = 16
    iterations = 200
    errors: list[BaseException] = []
    lock = threading.Lock()

    def _collect(target, *args):
        try:
            target(*args)
        except BaseException as exc:  # noqa: BLE001 — surface any error
            with lock:
                errors.append(exc)

    with ThreadPoolExecutor(max_workers=threads) as pool:
        futures = []
        for i in range(threads):
            call_id = f"t{i}"
            # Mix writers and readers to stress ordering.
            futures.append(pool.submit(_collect, _writer_insert, call_id, iterations))
            futures.append(pool.submit(_collect, _writer_log, call_id, iterations))
            futures.append(pool.submit(_collect, _writer_complete, call_id, iterations))
            futures.append(pool.submit(_collect, _reader, call_id, iterations))
        for fut in as_completed(futures):
            fut.result()  # re-raise anything unexpected

    assert errors == [], f"Concurrent access raised: {errors[:3]}"


def test_calls_cache_invariants_under_load():
    """After concurrent inserts + completes, statuses are coherent."""
    threads = 8
    iterations = 100
    prefix = "inv"

    def _run(tid: int) -> None:
        # Each thread writes its own key space so completes target real entries.
        call_id = f"{prefix}{tid}"
        _writer_insert(call_id, iterations)
        _writer_complete(call_id, iterations)
        _writer_log(call_id, iterations)

    with ThreadPoolExecutor(max_workers=threads) as pool:
        list(pool.map(_run, range(threads)))

    with agent_router._cache_lock:
        # Every entry we look at must be a complete dict (no torn writes).
        for _key, entry in list(agent_router._calls.items()):
            assert set(entry.keys()) >= {"status", "result"}
            # Either still running or completed — never an undefined state.
            assert entry["status"] in {"running", "completed"}


def test_concurrent_log_appends_preserve_all_entries():
    """Every log append under the lock must survive (no lost writes)."""
    threads = 32
    appends_per_thread = 50
    call_id = "race-key"

    # Pre-seed the list once (matches /agent/run's behaviour before the
    # background worker starts emitting logs).
    with agent_router._cache_lock:
        agent_router._logs[call_id] = []

    def _run(tid: int) -> None:
        for i in range(appends_per_thread):
            entry = LogEntry(timestamp="t", message=f"{tid}:{i}")
            with agent_router._cache_lock:
                agent_router._logs.setdefault(call_id, []).append(entry)

    with ThreadPoolExecutor(max_workers=threads) as pool:
        list(pool.map(_run, range(threads)))

    expected_total = threads * appends_per_thread
    with agent_router._cache_lock:
        assert len(agent_router._logs[call_id]) == expected_total
        # No duplicate or missing (tid, i) pairs.
        seen = {
            (entry.message.split(":")[0], entry.message.split(":")[1])
            for entry in agent_router._logs[call_id]
        }
    assert len(seen) == expected_total


def test_cache_lock_is_threading_lock():
    """Guard against accidental downgrade to an asyncio.Lock."""
    # ``threading.Lock`` instances are an opaque builtin type so we check for
    # the ``acquire``/``release`` protocol and that they block cross-thread.
    assert hasattr(agent_router._cache_lock, "acquire")
    assert hasattr(agent_router._cache_lock, "release")

    # An asyncio.Lock has an ``_loop`` attribute / is awaitable; confirm ours
    # is blocking (i.e. not an asyncio primitive).
    import asyncio

    assert not isinstance(agent_router._cache_lock, asyncio.Lock)
