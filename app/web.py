"""Panel sunucusu: video (MJPEG), canlı olaylar (WebSocket), kontrol uç noktaları,
WebRTC sinyalleşmesi ve QoD bildirim alıcısı (sink)."""
import argparse
import asyncio
import json
import logging
from pathlib import Path

from aiohttp import WSMsgType, web

from app.events import EventBus
from app.orchestrator import Orchestrator, ScenarioBusy
from app.receiver import Receiver

STATIC = Path(__file__).parent / "static"
LINK_KBPS = 3000


def create_app(receiver, orch: Orchestrator, bus: EventBus, sample: bool = True) -> web.Application:
    tasks: set[asyncio.Task] = set()

    def spawn(coro) -> None:
        t = asyncio.create_task(coro)
        tasks.add(t)
        t.add_done_callback(tasks.discard)

    async def index(_):
        return web.FileResponse(STATIC / "index.html")

    async def video(request):
        resp = web.StreamResponse(headers={"Content-Type": "multipart/x-mixed-replace; boundary=frame",
                                           "Cache-Control": "no-cache"})
        await resp.prepare(request)
        try:
            while True:
                jpg = receiver.latest_jpeg()
                if jpg:
                    await resp.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n")
                await asyncio.sleep(1 / 15)
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        return resp

    async def ws(request):
        sock = web.WebSocketResponse(heartbeat=20)
        await sock.prepare(request)
        q = bus.subscribe()
        try:
            await sock.send_json({"type": "snapshot", "events": bus.history})
            while not sock.closed:
                await sock.send_json(await q.get())
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            bus.unsubscribe(q)
        return sock

    async def notifications(request):
        await orch.handle_notification(await request.json())
        return web.Response(status=204)

    async def scenario(request):
        policy = request.match_info["policy"]
        if policy not in ("P2", "P3"):
            return web.json_response({"error": "bilinmeyen politika"}, status=400)
        if orch.busy:
            return web.json_response({"error": "senaryo zaten çalışıyor"}, status=409)

        async def run():
            try:
                await orch.run_scenario(policy)
            except ScenarioBusy:
                pass
            except Exception as e:  # senaryo hatası paneli düşürmesin
                bus.publish({"type": "error", "message": f"senaryo hatası: {e}"})
        spawn(run())
        return web.json_response({"ok": True, "policy": policy}, status=202)

    async def policy(request):
        p = request.match_info["policy"]
        if p not in ("P2", "P3"):
            return web.json_response({"error": "bilinmeyen politika"}, status=400)
        orch.set_policy(p)
        return web.json_response({"ok": True})

    async def load(request):
        if request.match_info["state"] == "on":
            orch.load.start()
        else:
            orch.load.stop()
        bus.publish({"type": "load", "on": request.match_info["state"] == "on"})
        return web.json_response({"ok": True})

    async def qod(request):
        if request.match_info["action"] == "request":
            sess = await orch.request_qod(orch.timeline.profile, orch.timeline.duration)
            if sess is None:
                return web.json_response({"error": "QoD isteği reddedildi (API kaydına bakın)"}, status=409)
        else:
            await orch.delete_qod()
        return web.json_response({"ok": True})

    async def sampler(app):
        async def loop():
            while True:
                await asyncio.sleep(1)
                stats = await receiver.update_stats()
                orch.record(stats)
                bus.publish({"type": "stats", **stats, "capacity_kbps": LINK_KBPS, "load": orch.load.on,
                             "policy": orch.policy})
        t = asyncio.create_task(loop())
        yield
        t.cancel()

    app = web.Application()
    app.add_routes([
        web.get("/", index), web.get("/video.mjpg", video), web.get("/ws", ws),
        web.post("/notifications", notifications),
        web.post("/api/scenario/{policy}", scenario), web.post("/api/policy/{policy}", policy),
        web.post("/api/load/{state}", load), web.post("/api/qod/{action}", qod),
        web.static("/static", STATIC),
    ])
    if hasattr(receiver, "handle_offer"):
        app.router.add_post("/offer", receiver.handle_offer)
    if sample:
        app.cleanup_ctx.append(sampler)
    return app


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--qod-url", default="http://127.0.0.1:9091")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    bus = EventBus()
    rx = Receiver()
    orch = Orchestrator(a.qod_url, rx, bus, sink_url=f"http://127.0.0.1:{a.port}/notifications")
    web.run_app(create_app(rx, orch, bus), port=a.port, access_log=None)


if __name__ == "__main__":
    main()
