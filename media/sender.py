"""Edge cihazdaki video göndericisi (edge namespace'inde çalışır).

Sentetik görüntüyü H.264 ile gönderir; hızını alıcıdan gelen GCC geri bildirimi (REMB) belirler.
"""
import argparse
import asyncio
import logging

import aiohttp
from aiortc import RTCConfiguration, RTCPeerConnection, RTCRtpSender, RTCSessionDescription

import aiortc.codecs.h264 as h264_codec

from media.source import SyntheticTrack


async def run(server: str, width: int, height: int, fps: int, max_kbps: int) -> None:
    # Kodlayıcı üst sınırı: profil hızının (2,5 Mbps) biraz üstü, bağlantının (3 Mbps) altı.
    # Böylece video boş ağda bağlantıyı tek başına doldurup kendi kuyruğunu şişirmez.
    h264_codec.MAX_BITRATE = max_kbps * 1000
    pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    transceiver = pc.addTransceiver(SyntheticTrack(width, height, fps), direction="sendonly")
    h264 = [c for c in RTCRtpSender.getCapabilities("video").codecs if c.mimeType == "video/H264"]
    transceiver.setCodecPreferences(h264)
    await pc.setLocalDescription(await pc.createOffer())
    async with aiohttp.ClientSession() as s:
        async with s.post(server, json={"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}) as r:
            answer = await r.json()
    await pc.setRemoteDescription(RTCSessionDescription(**answer))
    done = asyncio.Event()

    @pc.on("connectionstatechange")
    def _state():
        logging.info("bağlantı: %s", pc.connectionState)
        if pc.connectionState in ("failed", "closed"):
            done.set()

    await done.wait()
    await pc.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://10.10.2.2:8080/offer")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=360)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--max-kbps", type=int, default=2600)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(a.server, a.width, a.height, a.fps, a.max_kbps))


if __name__ == "__main__":
    main()
