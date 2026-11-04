"""Demo ölçümleri. Örnekler (zaman_sn, değer) çiftleri; değer None olabilir."""
Samples = list[tuple[float, float | None]]


def time_to_target(samples: Samples, t_avail: float, target_kbps: int, frac: float = 0.9,
                   hold: int = 1) -> float | None:
    """QoD AVAILABLE anından, alınan hızın hedefin %90'ına ulaşıp `hold` örnek boyunca orada
    kaldığı ilk ana kadar geçen süre. hold > 1, kuyruk boşalmasının kısa patlamasını eler."""
    after = [(t, v) for t, v in samples if t >= t_avail]
    for i in range(len(after) - hold + 1):
        window = after[i:i + hold]
        if all(v is not None and v >= frac * target_kbps for _, v in window):
            return float(window[0][0] - t_avail)
    return None


def priority_utilization(samples: Samples, t_start: float, t_end: float, target_kbps: int) -> float:
    """Oturum boyunca alınan ortalama hızın profil hızına oranı (0-1)."""
    vals = [v for t, v in samples if t_start <= t <= t_end and v is not None]
    if not vals or target_kbps <= 0:
        return 0.0
    return min(1.0, sum(vals) / len(vals) / target_kbps)


def closing_spike(samples_e2e: Samples, t_end: float, window_s: float = 5.0) -> float:
    """Oturum bittikten sonraki pencerede görülen en yüksek uçtan uca gecikme (ms)."""
    vals = [v for t, v in samples_e2e if t_end < t <= t_end + window_s and v is not None]
    return float(max(vals)) if vals else 0.0
