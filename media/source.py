"""Kamera yerine sentetik video: hareketli desen + kareye gömülü gönderim zamanı.

Zaman damgası 2 satır x 32 blok (16x16 piksel) siyah/beyaz bit olarak sol üste yazılır:
8 bitlik işaret + 56 bit milisaniye. Büyük bloklar düşük bit hızında H.264'ten sağ çıkar.
"""
import time

import av
import numpy as np
from aiortc import VideoStreamTrack

BLOCK, COLS, ROWS = 16, 32, 2
MARKER = 0b10110010
NOISE_TOP = 270  # 360 piksellik karenin alt 90 satırı


def _bits(stamp_ms: int) -> list[int]:
    value = (MARKER << 56) | (stamp_ms & ((1 << 56) - 1))
    return [(value >> (63 - i)) & 1 for i in range(64)]


def draw_stamp(img: np.ndarray, stamp_ms: int) -> None:
    for i, b in enumerate(_bits(stamp_ms)):
        r, c = divmod(i, COLS)
        img[r * BLOCK:(r + 1) * BLOCK, c * BLOCK:(c + 1) * BLOCK] = 255 if b else 0


def decode_stamp(frame: av.VideoFrame) -> int | None:
    gray = frame.to_ndarray(format="gray")
    value = 0
    for i in range(64):
        r, c = divmod(i, COLS)
        cell = gray[r * BLOCK + 4:(r + 1) * BLOCK - 4, c * BLOCK + 4:(c + 1) * BLOCK - 4]
        value = (value << 1) | int(cell.mean() > 128)
    if value >> 56 != MARKER:
        return None
    return value & ((1 << 56) - 1)


class SyntheticTrack(VideoStreamTrack):
    """Hareketli renkli şeritler ve sağdan sola kayan bir kutu; her karede gönderim zamanı."""

    def __init__(self, width: int = 640, height: int = 360, fps: int = 30):
        super().__init__()
        self.width, self.height, self.fps = width, height, fps
        self.n = 0
        self.last_stamp_ms: int | None = None
        x = np.arange(width)
        self._rng = np.random.default_rng(1)
        self._bands = (np.stack([x * 0.4, 128 + 0 * x, 255 - x * 0.4], -1) % 256).astype(np.uint8)

    async def recv(self) -> av.VideoFrame:
        pts, time_base = await self.next_timestamp()
        img = np.empty((self.height, self.width, 3), np.uint8)
        img[:] = np.roll(self._bands, self.n * 4, axis=0)[None, :, :]
        box = (self.n * 6) % (self.width + 120) - 120
        img[140:260, max(box, 0):max(box + 120, 0)] = (250, 200, 40)
        # Alt bant: her karede değişen ayrıntılı doku. Gerçek kameradaki ayrıntıyı temsil eder,
        # kodlayıcının profil hızını (2,5 Mbps) doldurabilmesini sağlar.
        h = self.height - NOISE_TOP
        img[NOISE_TOP:] = self._rng.integers(0, 256, (h, self.width, 1), np.uint8)
        self.last_stamp_ms = int(time.time() * 1000)
        draw_stamp(img, self.last_stamp_ms)
        self.n += 1
        frame = av.VideoFrame.from_ndarray(img, format="rgb24")
        frame.pts, frame.time_base = pts, time_base
        return frame
