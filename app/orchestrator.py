"""Uygulama tarafı: CAMARA QoD istemcisi, bildirim (sink) işleyici, P2/P3 politikası ve senaryo.

P2: gönderici QoD'den habersiz; GCC kendi ölçümüyle tepki verir.
P3: AVAILABLE bildirimi gelince GCC tahmini profil hızına çekilir; bitişten `predrop_s` önce
QoD öncesi hıza indirilir.
"""
import asyncio
import json
import logging
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import aiohttp

from app.metrics import closing_spike, priority_utilization, time_to_target

log = logging.getLogger("orchestrator")
DEVICE_IP, SERVER_IP, LOAD_IP = "10.10.1.2", "10.10.2.2", "10.10.2.3"
QOD = "/quality-on-demand/v1"
# Profil hızı ağ katmanı (IP) hızıdır. Medya bunun %90'ını kullanabilir; kalan pay paket
# başlıkları ve yeniden gönderimler içindir. P3 hedefi ve ölçümler bu değere göre yapılır.
MEDIA_SHARE = 0.9


class ScenarioBusy(Exception):
    pass


@dataclass
class Timeline:
    load_at: float = 10
    qod_at: float = 20
    duration: int = 30
    tail: float = 14
    predrop_s: float = 4
    profile: str = "QOS_VIDEO_L"


@dataclass
class RunResult:
    policy: str
    target_kbps: int | None
    t_to_target_s: float | None
    max_kbps: float
    utilization: float
    closing_spike_ms: float


class IperfLoad:
    """'Diğer kullanıcılar': others namespace'inden yük hedefine TCP toplu yükleme."""

    def __init__(self):
        self._procs: list[subprocess.Popen] = []

    def start(self) -> None:
        if self._procs:
            return
        self._procs.append(subprocess.Popen(["iperf3", "-s", "-B", LOAD_IP], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        time.sleep(0.3)
        self._procs.append(subprocess.Popen(["ip", "netns", "exec", "others", "iperf3", "-c", LOAD_IP, "-t", "3600", "-P", "4"],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    def stop(self) -> None:
        for p in reversed(self._procs):
            p.terminate()
        self._procs.clear()

    @property
    def on(self) -> bool:
        return bool(self._procs)


class Orchestrator:
    def __init__(self, qod_url, receiver, events, load=None, token="demo-token",
                 sink_url="http://127.0.0.1:8080/notifications", runs_dir="runs"):
        self.qod_url, self.receiver, self.events = qod_url.rstrip("/"), receiver, events
        self.load = load or IperfLoad()
        self.token, self.sink_url = token, sink_url
        self.runs_dir = Path(runs_dir) if runs_dir else None
        self.policy = "P2"
        self.timeline = Timeline()
        self.session_id: str | None = None
        self.target_kbps: int | None = None
        self.t_request = self.t_avail = self.t_end = None
        self.rx: list[tuple[float, float | None]] = []
        self.e2e: list[tuple[float, float | None]] = []
        self._ended = asyncio.Event()
        self._predrop: asyncio.Task | None = None
        self._busy = False

    # --- yardımcılar ---------------------------------------------------------
    def set_policy(self, policy: str) -> None:
        if policy not in ("P2", "P3"):
            raise ValueError(policy)
        self.policy = policy
        self.events.publish({"type": "policy", "policy": policy})

    def record(self, stats: dict) -> None:
        now = time.time()
        self.rx.append((now, stats.get("rx_kbps")))
        self.e2e.append((now, stats.get("e2e_ms")))
        del self.rx[:-900], self.e2e[:-900]

    async def _api(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict | list | None]:
        headers = {"Authorization": f"Bearer {self.token}"}
        async with aiohttp.ClientSession() as s:
            async with s.request(method, self.qod_url + path, json=body, headers=headers) as r:
                data = await r.json() if r.content_type == "application/json" else None
                status = r.status
        self.events.publish({"type": "api_log", "method": method, "path": path, "request": body,
                             "status": status, "response": data})
        return status, data

    # --- CAMARA QoD istemcisi ------------------------------------------------
    async def request_qod(self, profile: str, duration: int) -> dict | None:
        status, prof = await self._api("GET", f"/qos-profiles/v1/qos-profiles/{profile}")
        if status != 200:
            return None
        body = {
            "device": {"ipv4Address": {"publicAddress": DEVICE_IP, "privateAddress": DEVICE_IP}},
            "applicationServer": {"ipv4Address": SERVER_IP},
            "qosProfile": profile, "duration": duration, "sink": self.sink_url,
        }
        self.t_request = time.time()
        status, sess = await self._api("POST", f"{QOD}/sessions", body)
        if status != 201:
            return None
        self.session_id, self.target_kbps = sess["sessionId"], prof["maxUpstreamRate"]["value"]
        self.t_avail = self.t_end = None
        self._ended.clear()
        self.events.publish({"type": "qod_state", "qosStatus": sess["qosStatus"], "targetKbps": self.target_kbps})
        return sess

    @property
    def media_kbps(self) -> int | None:
        return int(self.target_kbps * MEDIA_SHARE) if self.target_kbps else None

    async def get_session(self) -> dict | None:
        if not self.session_id:
            return None
        status, sess = await self._api("GET", f"{QOD}/sessions/{self.session_id}")
        return sess if status == 200 else None

    async def delete_qod(self) -> None:
        if self.session_id:
            await self._api("DELETE", f"{QOD}/sessions/{self.session_id}")

    async def handle_notification(self, event: dict) -> None:
        self.events.publish({"type": "api_log", "method": "BİLDİRİM", "path": "/notifications", "request": event,
                             "status": None, "response": None})
        data = event.get("data", {})
        if data.get("sessionId") != self.session_id:
            return
        status = data.get("qosStatus")
        state = {"type": "qod_state", "qosStatus": status, "statusInfo": data.get("statusInfo"),
                 "targetKbps": self.target_kbps, "mediaKbps": self.media_kbps}
        if status == "AVAILABLE":
            self.t_avail = time.time()
            sess = await self.get_session()
            exp_txt = (sess or {}).get("expiresAt")
            expires = datetime.fromisoformat(exp_txt.replace("Z", "+00:00")).timestamp() if exp_txt else None
            state["expiresAt"] = exp_txt
            if self.policy == "P3":
                self.receiver.set_gcc_estimate(self.media_kbps)
                self.events.publish({"type": "p3", "action": "hızı profil hızına çek", "kbps": self.media_kbps})
                if expires:
                    self._predrop = asyncio.create_task(self._predrop_at(expires - self.timeline.predrop_s))
        elif status == "UNAVAILABLE":
            self.t_end = time.time()
            if self._predrop:
                self._predrop.cancel()
            self.session_id = None
            self._ended.set()
        self.events.publish(state)

    async def _predrop_at(self, when: float) -> None:
        await asyncio.sleep(max(0.0, when - time.time()))
        before = [v for t, v in self.rx if self.t_request and self.t_request - 5 <= t < self.t_request and v]
        kbps = int(sum(before) / len(before)) if before else int((self.target_kbps or 1000) / 2)
        self.receiver.set_gcc_estimate(kbps)
        self.events.publish({"type": "p3", "action": "bitişten önce hızı düşür", "kbps": kbps})

    # --- senaryo -------------------------------------------------------------
    async def run_scenario(self, policy: str) -> RunResult | None:
        if self._busy:
            raise ScenarioBusy("senaryo zaten çalışıyor")
        self._busy = True
        tl = self.timeline
        try:
            self.set_policy(policy)
            t0 = time.time()
            self.events.publish({"type": "scenario", "policy": policy, "phase": "başladı"})
            await asyncio.sleep(tl.load_at)
            self.load.start()
            self.events.publish({"type": "load", "on": True})
            await asyncio.sleep(tl.qod_at - tl.load_at)
            if await self.request_qod(tl.profile, tl.duration) is None:
                self.events.publish({"type": "scenario", "policy": policy, "phase": "QoD isteği başarısız"})
                return None
            await asyncio.wait_for(self._ended.wait(), tl.duration + 15)
            await asyncio.sleep(tl.tail)
            result = self._result(policy)
            self._save(t0, result)
            self.events.publish({"type": "result", **asdict(result)})
            return result
        finally:
            self.load.stop()
            self.events.publish({"type": "load", "on": False})
            self._busy = False

    def _result(self, policy: str) -> RunResult:
        target = self.media_kbps or 0
        during = [v for t, v in self.rx if self.t_avail and self.t_end and self.t_avail <= t <= self.t_end and v]
        return RunResult(
            policy=policy, target_kbps=self.media_kbps,
            t_to_target_s=time_to_target(self.rx, self.t_avail or 0, target, hold=3) if self.t_avail else None,
            max_kbps=max(during, default=0.0),
            utilization=round(priority_utilization(self.rx, self.t_avail or 0, self.t_end or 0, target), 3),
            closing_spike_ms=closing_spike(self.e2e, self.t_end or 0),
        )

    def _save(self, t0: float, result: RunResult) -> None:
        if not self.runs_dir:
            return
        self.runs_dir.mkdir(exist_ok=True)
        name = datetime.fromtimestamp(t0).strftime("%Y%m%d-%H%M%S") + f"-{result.policy}.json"
        rec = {"result": asdict(result), "timeline": asdict(self.timeline), "t0": t0,
               "t_request": self.t_request, "t_avail": self.t_avail, "t_end": self.t_end,
               "rx_kbps": [x for x in self.rx if x[0] >= t0], "e2e_ms": [x for x in self.e2e if x[0] >= t0],
               "api_log": [e for e in self.events.history if e["type"] == "api_log" and e["t"] >= t0]}
        (self.runs_dir / name).write_text(json.dumps(rec, ensure_ascii=False, indent=1))
