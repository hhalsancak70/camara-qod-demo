import pytest
from qod.server import make_app
from qod.sessions import SessionStore
from tests.conftest import session_body

AUTH = {"Authorization": "Bearer demo-token"}
QOD = "/quality-on-demand/v1"


@pytest.fixture
async def client(aiohttp_client, shaper, clock):
    store = SessionStore(shaper, clock, activation_delay_s=1.0)
    return await aiohttp_client(make_app(store, token="demo-token", tick_interval=None))


async def test_create_returns_201(client):
    r = await client.post(f"{QOD}/sessions", json=session_body(), headers=AUTH)
    assert r.status == 201
    body = await r.json()
    assert body["sessionId"] and body["qosStatus"] == "REQUESTED"


async def test_second_create_conflict(client):
    await client.post(f"{QOD}/sessions", json=session_body(), headers=AUTH)
    r = await client.post(f"{QOD}/sessions", json=session_body(), headers=AUTH)
    assert r.status == 409
    assert (await r.json())["code"] == "CONFLICT"
    assert (await r.json())["status"] == 409


async def test_missing_token_401(client):
    r = await client.post(f"{QOD}/sessions", json=session_body())
    assert r.status == 401
    assert (await r.json())["code"] == "UNAUTHENTICATED"


async def test_missing_device_422(client):
    body = session_body()
    del body["device"]
    r = await client.post(f"{QOD}/sessions", json=body, headers=AUTH)
    assert r.status == 422
    assert (await r.json())["code"] == "MISSING_IDENTIFIER"


async def test_get_unknown_404(client):
    r = await client.get(f"{QOD}/sessions/00000000-0000-0000-0000-000000000000", headers=AUTH)
    assert r.status == 404
    assert (await r.json())["code"] == "NOT_FOUND"


async def test_delete_204(client):
    sid = (await (await client.post(f"{QOD}/sessions", json=session_body(), headers=AUTH)).json())["sessionId"]
    r = await client.delete(f"{QOD}/sessions/{sid}", headers=AUTH)
    assert r.status == 204
    assert (await client.get(f"{QOD}/sessions/{sid}", headers=AUTH)).status == 404


async def test_invalid_json_400(client):
    r = await client.post(f"{QOD}/sessions", data="{bozuk", headers={**AUTH, "Content-Type": "application/json"})
    assert r.status == 400
    assert (await r.json())["code"] == "INVALID_ARGUMENT"


async def test_retrieve_profiles(client):
    r = await client.post("/qos-profiles/v1/retrieve-qos-profiles", json={}, headers=AUTH)
    assert r.status == 200
    profiles = {p["name"]: p for p in await r.json()}
    assert set(profiles) == {"QOS_VIDEO_M", "QOS_VIDEO_L"}
    assert profiles["QOS_VIDEO_L"]["maxUpstreamRate"] == {"value": 2500, "unit": "kbps"}


async def test_retrieve_sessions_by_device(client):
    await client.post(f"{QOD}/sessions", json=session_body(), headers=AUTH)
    r = await client.post(f"{QOD}/retrieve-sessions", json={"device": session_body()["device"]}, headers=AUTH)
    assert r.status == 200 and len(await r.json()) == 1
