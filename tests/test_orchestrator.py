import asyncio

import pytest

from app.events import EventBus
from app.orchestrator import Orchestrator, ScenarioBusy, Timeline
from qod.server import cloud_event, make_app
from qod.sessions import SessionStore
from qod.shaper import FakeShaper


class FakeReceiver:
    def __init__(self):
        self.estimates: list[int] = []

    def set_gcc_estimate(self, kbps: int) -> None:
        self.estimates.append(kbps)


class FakeLoad:
    def __init__(self):
        self.on = False

    def start(self):
        self.on = True

    def stop(self):
        self.on = False


@pytest.fixture
async def qod_url(aiohttp_server):
    import time
    store = SessionStore(FakeShaper(), time.time, activation_delay_s=0.0)
    server = await aiohttp_server(make_app(store, tick_interval=0.02))
    return str(server.make_url("")).rstrip("/")


def make_orch(qod_url, policy):
    rx = FakeReceiver()
    o = Orchestrator(qod_url, rx, EventBus(), load=FakeLoad(), runs_dir=None)
    o.set_policy(policy)
    return o, rx


async def available_event(o: Orchestrator) -> dict:
    sess = await o.get_session()
    sess["qosStatus"] = "AVAILABLE"
    return cloud_event(sess)


async def test_p3_sets_estimate_on_available(qod_url):
    o, rx = make_orch(qod_url, "P3")
    await o.request_qod("QOS_VIDEO_L", 30)
    await o.handle_notification(await available_event(o))
    assert rx.estimates == [2250]  # profil 2500 kbps x 0,9 medya payı


async def test_p2_never_touches_estimate(qod_url):
    o, rx = make_orch(qod_url, "P2")
    await o.request_qod("QOS_VIDEO_L", 30)
    await o.handle_notification(await available_event(o))
    assert rx.estimates == []


async def test_conflict_is_reported_not_raised(qod_url):
    o, _ = make_orch(qod_url, "P2")
    await o.request_qod("QOS_VIDEO_L", 30)
    assert await o.request_qod("QOS_VIDEO_L", 30) is None
    assert any(e.get("status") == 409 for e in o.events.history if e["type"] == "api_log")


async def test_scenario_rejects_parallel_run(qod_url):
    o, _ = make_orch(qod_url, "P2")
    o.timeline = Timeline(load_at=5, qod_at=10, duration=30, tail=1)
    task = asyncio.create_task(o.run_scenario("P2"))
    await asyncio.sleep(0.05)
    with pytest.raises(ScenarioBusy):
        await o.run_scenario("P3")
    task.cancel()
