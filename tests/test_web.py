import pytest

from app.events import EventBus
from app.orchestrator import Orchestrator, Timeline
from app.web import create_app
from tests.test_orchestrator import FakeLoad, FakeReceiver


@pytest.fixture
async def client(aiohttp_client):
    rx = FakeReceiver()
    rx.latest_jpeg = lambda: None
    orch = Orchestrator("http://127.0.0.1:1", rx, EventBus(), load=FakeLoad(), runs_dir=None)
    orch.timeline = Timeline(load_at=30, qod_at=40)
    return await aiohttp_client(create_app(rx, orch, orch.events, sample=False))


async def test_index_served(client):
    r = await client.get("/")
    assert r.status == 200
    text = await r.text()
    assert "Ağ: Raspberry Pi üzerinde emüle edilmiş 3 Mbps mobil uplink (Linux tc). QoD API: CAMARA QoD 1.1.0 uyumlu yerel servis." in text


async def test_second_scenario_rejected(client):
    assert (await client.post("/api/scenario/P2")).status == 202
    r = await client.post("/api/scenario/P3")
    assert r.status == 409
    assert (await r.json())["error"] == "senaryo zaten çalışıyor"


async def test_unknown_policy_400(client):
    assert (await client.post("/api/policy/P9")).status == 400


async def test_load_toggle(client):
    assert (await client.post("/api/load/on")).status == 200
    assert (await client.post("/api/load/off")).status == 200
