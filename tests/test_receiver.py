from aiortc.rate import RemoteBitrateEstimator

from app.receiver import apply_estimate


def test_apply_estimate_sets_rate_and_clears_congestion_memory():
    est = RemoteBitrateEstimator()
    rc = est.rate_control
    rc.near_max, rc.avg_max_bitrate_kbps = True, 500.0
    old_detector = est.detector
    apply_estimate(est, 2500, now_ms=1_000)
    assert rc.current_bitrate == 2_500_000
    assert rc.current_bitrate_initialized
    assert rc.near_max is False and rc.avg_max_bitrate_kbps is None
    assert est.detector is not old_detector
