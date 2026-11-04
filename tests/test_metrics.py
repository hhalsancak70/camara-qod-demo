from app.metrics import closing_spike, priority_utilization, time_to_target


def test_time_to_target_reached():
    assert time_to_target([(0, 500), (5, 1500), (10, 2300)], 0, 2500) == 10.0


def test_time_to_target_counts_from_available():
    assert time_to_target([(20, 2400), (24, 2300)], 21, 2500) == 3.0


def test_time_to_target_never_reached_is_none():
    assert time_to_target([(0, 500), (5, 900)], 0, 2500) is None


def test_time_to_target_no_samples_is_none():
    assert time_to_target([], 0, 2500) is None


def test_priority_utilization_half():
    samples = [(t, 1250) for t in range(0, 31)]
    assert priority_utilization(samples, 0, 30, 2500) == 0.5


def test_priority_utilization_no_samples_is_zero():
    assert priority_utilization([], 0, 30, 2500) == 0.0


def test_closing_spike():
    assert closing_spike([(49, 80), (52, 900), (57, 120)], 50) == 900


def test_closing_spike_ignores_missing_values():
    assert closing_spike([(51, None), (52, 300)], 50) == 300
    assert closing_spike([], 50) == 0.0


def test_time_to_target_ignores_short_burst():
    """QoD açılınca eski kuyruğun boşalması kısa bir patlama yapar; bu 'ulaştı' sayılmaz."""
    samples = [(0, 2400), (1, 600), (2, 700), (3, 2300), (4, 2350), (5, 2400)]
    assert time_to_target(samples, 0, 2500, hold=3) == 3.0
