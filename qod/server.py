"""CAMARA QoD 1.1.0 ve QoS Profiles uç noktalarını sunan yerel HTTP servisi.

Laboratuvar sapmaları: yetkilendirme sabit bearer token ile; sink için http kabul edilir.
"""
import argparse
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone

from aiohttp import ClientSession, ClientTimeout, web

from qod.profiles import PROFILES
from qod.sessions import QodError, SessionStore, device_ip

log = logging.getLogger("qod")
QOD = "/quality-on-demand/v1"
PROF = "/qos-profiles/v1"
EVENT_TYPE = "org.camaraproject.quality-on-demand.v1.qos-status-changed"


def _err(status: int, code: str, message: str) -> web.Response:
    return web.json_response({"status": status, "code": code, "message": message}, status=status)


def cloud_event(session: dict) -> dict:
    data = {"sessionId": session["sessionId"], "qosStatus": session["qosStatus"]}
    if session.get("statusInfo"):
        data["statusInfo"] = session["statusInfo"]
    return {
        "id": str(uuid.uuid4()), "source": "qod-demo", "specversion": "1.0", "type": EVENT_TYPE,
        "time": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "datacontenttype": "application/json", "data": data,
    }


def make_app(store: SessionStore, token: str = "demo-token", tick_interval: float | None = 0.2) -> web.Application:
    @web.middleware
    async def guard(request, handler):
        if request.headers.get("Authorization") != f"Bearer {token}":
            return _err(401, "UNAUTHENTICATED", "Request not authenticated due to missing, invalid, or expired credentials.")
        try:
            return await handler(request)
        except QodError as e:
            return _err(e.status, e.code, e.message)

    async def body(request) -> dict:
        try:
            data = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise InvalidJson()
        if not isinstance(data, dict):
            raise InvalidJson()
        return data

    async def create(request):
        return web.json_response(store.create(await body(request)), status=201)

    async def get(request):
        return web.json_response(store.get(request.match_info["sid"]))

    async def delete(request):
        store.delete(request.match_info["sid"])
        return web.Response(status=204)

    async def extend(request):
        add = (await body(request)).get("requestedAdditionalDuration")
        return web.json_response(store.extend(request.match_info["sid"], add))

    async def retrieve(request):
        return web.json_response(store.by_device(device_ip((await body(request)).get("device"))))

    async def profiles(request):
        return web.json_response([p.to_camara() for p in PROFILES.values()])

    async def profile(request):
        p = PROFILES.get(request.match_info["name"])
        if p is None:
            return _err(404, "NOT_FOUND", "The specified resource is not found.")
        return web.json_response(p.to_camara())

    app = web.Application(middlewares=[guard])
    app.add_routes([
        web.post(f"{QOD}/sessions", create),
        web.get(f"{QOD}/sessions/{{sid}}", get),
        web.delete(f"{QOD}/sessions/{{sid}}", delete),
        web.post(f"{QOD}/sessions/{{sid}}/extend", extend),
        web.post(f"{QOD}/retrieve-sessions", retrieve),
        web.post(f"{PROF}/retrieve-qos-profiles", profiles),
        web.get(f"{PROF}/qos-profiles/{{name}}", profile),
    ])

    pending: set[asyncio.Task] = set()

    def on_change(session: dict) -> None:
        sink = session.get("sink")
        if sink:
            t = asyncio.get_event_loop().create_task(_notify(sink, cloud_event(session)))
            pending.add(t)
            t.add_done_callback(pending.discard)

    store.on_change = on_change

    async def ticker(app):
        async def loop():
            while True:
                store.tick()
                await asyncio.sleep(tick_interval)
        task = asyncio.create_task(loop())
        yield
        task.cancel()

    if tick_interval:
        app.cleanup_ctx.append(ticker)
    return app


class InvalidJson(QodError):
    def __init__(self):
        super().__init__("Client specified an invalid argument, request body or query param.")


async def _notify(sink: str, event: dict) -> None:
    try:
        async with ClientSession(timeout=ClientTimeout(total=3)) as s:
            await s.post(sink, json=event, headers={"Content-Type": "application/cloudevents+json"})
    except Exception as e:  # bildirim başarısız olsa da servis çalışmaya devam eder
        log.warning("bildirim gönderilemedi (%s): %s", sink, e)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9091)
    ap.add_argument("--activation-delay", type=float, default=1.0)
    ap.add_argument("--fake-shaper", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    from qod.shaper import FakeShaper, TcShaper
    shaper = FakeShaper() if a.fake_shaper else TcShaper()
    web.run_app(make_app(SessionStore(shaper, time.time, a.activation_delay)), port=a.port)


if __name__ == "__main__":
    main()
