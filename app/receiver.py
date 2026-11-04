"""Uygulama sunucusundaki video alıcısı: aiortc + GCC alıcı tarafı (REMB) + ölçümler.

P3 kancası `set_gcc_estimate`: alıcının GCC tahminini dışarıdan ayarlar; bir sonraki REMB ile
gönderici bu hıza geçer. aiortc bu alanları özel tuttuğu için erişim `_estimator()`'da toplanır
(aiortc 1.15.0'a sabit).
"""
import asyncio
import io
import logging
import time

import aioice.ice
from aiohttp import web
from aiortc import clock as aiortc_clock
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription

from aiortc.rate import OveruseDetector, OveruseEstimator

from media.source import decode_stamp

log = logging.getLogger("receiver")
SERVER_IP = "10.10.2.2"

# ICE yalnızca video sunucusu adresini kullansın: QoD filtresi bu adresle eşleşir.
_orig_hosts = aioice.ice.get_host_addresses


def _server_only(use_ipv4: bool, use_ipv6: bool) -> list[str]:
    hosts = _orig_hosts(use_ipv4=use_ipv4, use_ipv6=use_ipv6)
    return [a for a in hosts if a == SERVER_IP] or hosts


aioice.ice.get_host_addresses = _server_only


def apply_estimate(est, kbps: int, now_ms: int) -> None:
    """P3: GCC tahminini dışarıdan ayarla ve tıkanıklık hafızasını sıfırla.

    QoD açılınca eski kuyruğun boşalması gecikmeyi geçici olarak artırır; GCC bunu tıkanıklık
    sanıp hızı hemen kesmesin diye gecikme dedektörü ve 'eski azami hız' hafızası temizlenir.
    """
    rc = est.rate_control
    rc.set_estimate(int(kbps * 1000), now_ms)
    rc.avg_max_bitrate_kbps, rc.near_max = None, False
    est.detector, est.estimator = OveruseDetector(), OveruseEstimator()


class Receiver:
    def __init__(self):
        self.pc: RTCPeerConnection | None = None
        self._latest = None          # son çözülen kare
        self._latest_n = 0
        self._jpeg = (None, -1)      # (bayt, kare no)
        self._frames: list[float] = []
        self._e2e: list[tuple[float, float]] = []
        self._last_pkts = 0
        self._last_lost = 0
        self._stats = {"rx_kbps": 0.0, "e2e_ms": None, "fps": 0.0, "loss_pct": 0.0, "remb_kbps": None}

    # --- sinyalleşme ---------------------------------------------------------
    async def handle_offer(self, request: web.Request) -> web.Response:
        params = await request.json()
        if self.pc is not None:
            await self.pc.close()
        pc = self.pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))

        @pc.on("track")
        def on_track(track):
            if track.kind == "video":
                asyncio.ensure_future(self._consume(track))

        await pc.setRemoteDescription(RTCSessionDescription(sdp=params["sdp"], type=params["type"]))
        await pc.setLocalDescription(await pc.createAnswer())
        return web.json_response({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})

    async def _consume(self, track) -> None:
        while True:
            try:
                frame = await track.recv()
            except Exception:
                return
            now = time.time()
            self._latest, self._latest_n = frame, self._latest_n + 1
            self._frames.append(now)
            stamp = decode_stamp(frame)
            if stamp is not None:
                self._e2e.append((now, now * 1000 - stamp))

    # --- ölçümler ------------------------------------------------------------
    def _estimator(self):
        if self.pc is None:
            return None
        for r in self.pc.getReceivers():
            if r.track and r.track.kind == "video":
                return getattr(r, "_RTCRtpReceiver__remote_bitrate_estimator", None)
        return None

    async def update_stats(self) -> dict:
        """Saniyede bir çağrılır; son 1 sn penceresindeki değerleri günceller."""
        now = time.time()
        self._frames = [t for t in self._frames if now - t <= 1.0]
        recent = [d for t, d in self._e2e if now - t <= 1.0]
        self._e2e = [x for x in self._e2e if now - x[0] <= 1.0]
        loss = 0.0
        if self.pc is not None:
            for st in (await self.pc.getStats()).values():
                if st.type == "inbound-rtp" and st.kind == "video":
                    got = st.packetsReceived - self._last_pkts
                    lost = max(0, st.packetsLost - self._last_lost)
                    loss = 100.0 * lost / (got + lost) if got + lost > 0 else 0.0
                    self._last_pkts, self._last_lost = st.packetsReceived, st.packetsLost
        est = self._estimator()
        rate = est.incoming_bitrate.rate(aiortc_clock.current_ms()) if est else None
        self._stats = {
            "rx_kbps": round((rate or 0) / 1000, 1),
            "e2e_ms": round(max(recent), 1) if recent else None,
            "fps": float(len(self._frames)),
            "loss_pct": round(loss, 2),
            "remb_kbps": round(est.rate_control.current_bitrate / 1000, 1) if est and est.rate_control.current_bitrate_initialized else None,
        }
        return self._stats

    def stats(self) -> dict:
        return dict(self._stats)

    def set_gcc_estimate(self, kbps: int) -> None:
        est = self._estimator()
        if est is None:
            log.warning("GCC tahmini ayarlanamadı: aktif video alıcısı yok")
            return
        apply_estimate(est, kbps, aiortc_clock.current_ms())

    def latest_jpeg(self) -> bytes | None:
        if self._latest is None:
            return None
        if self._jpeg[1] != self._latest_n:
            buf = io.BytesIO()
            self._latest.to_image().save(buf, format="JPEG", quality=70)
            self._jpeg = (buf.getvalue(), self._latest_n)
        return self._jpeg[0]
