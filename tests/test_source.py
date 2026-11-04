import av
from fractions import Fraction

from media.source import SyntheticTrack, decode_stamp


async def test_stamp_roundtrip_raw():
    track = SyntheticTrack()
    frame = await track.recv()
    assert (frame.width, frame.height) == (640, 360)
    assert decode_stamp(frame) == track.last_stamp_ms


async def test_stamp_survives_low_bitrate_h264():
    track = SyntheticTrack()
    enc = av.CodecContext.create("libx264", "w")
    enc.width, enc.height, enc.pix_fmt = 640, 360, "yuv420p"
    enc.bit_rate, enc.time_base = 250_000, Fraction(1, 30)
    enc.options = {"preset": "ultrafast", "tune": "zerolatency"}
    dec = av.CodecContext.create("h264", "r")
    stamps, decoded = [], []
    for i in range(30):
        f = await track.recv()
        stamps.append(track.last_stamp_ms)
        f = f.reformat(format="yuv420p")
        f.pts = i
        for pkt in enc.encode(f):
            decoded += [decode_stamp(d) for d in dec.decode(pkt)]
    assert len(decoded) >= 20
    assert all(s in stamps for s in decoded)


def test_unstamped_frame_returns_none():
    import numpy as np
    blank = av.VideoFrame.from_ndarray(np.full((360, 640, 3), 90, np.uint8), format="rgb24")
    assert decode_stamp(blank) is None


async def test_content_fills_target_bitrate():
    """Görüntü yeterince ayrıntılı olmalı ki kodlayıcı QoD profil hızını (2500 kbps) doldurabilsin."""
    track = SyntheticTrack()
    enc = av.CodecContext.create("libx264", "w")
    enc.width, enc.height, enc.pix_fmt = 640, 360, "yuv420p"
    enc.bit_rate, enc.time_base, enc.framerate = 2_500_000, Fraction(1, 30), Fraction(30, 1)
    enc.options = {"preset": "ultrafast", "tune": "zerolatency"}
    total = 0
    for i in range(60):
        f = (await track.recv()).reformat(format="yuv420p")
        f.pts = i
        total += sum(p.size for p in enc.encode(f))
    kbps = total * 8 / 2 / 1000  # 60 kare = 2 sn
    assert kbps >= 0.8 * 2500, kbps
