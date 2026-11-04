import pytest
from qod.sessions import SessionStore, ConflictError, DurationOutOfRange
from tests.conftest import session_body


@pytest.fixture
def store(shaper, clock):
    changes = []
    s = SessionStore(shaper, clock, activation_delay_s=1.0)
    s.on_change = changes.append
    s.changes = changes
    return s


def test_create_is_requested_then_available(store, shaper, clock):
    sess = store.create(session_body())
    assert sess["qosStatus"] == "REQUESTED"
    assert shaper.calls == []
    store.tick(clock.advance(1.0))
    got = store.get(sess["sessionId"])
    assert got["qosStatus"] == "AVAILABLE"
    assert got["startedAt"] and got["expiresAt"]
    assert store.expires_ts(sess["sessionId"]) == pytest.approx(clock.t + 30)
    assert shaper.calls == [("add", sess["sessionId"], "10.10.1.2", "10.10.2.2", 2500)]
    assert store.changes[-1]["qosStatus"] == "AVAILABLE"


def test_expiry(store, shaper, clock):
    sid = store.create(session_body())["sessionId"]
    store.tick(clock.advance(1.0))
    store.tick(clock.advance(31))
    got = store.get(sid)
    assert got["qosStatus"] == "UNAVAILABLE"
    assert got["statusInfo"] == "DURATION_EXPIRED"
    assert shaper.calls[-1] == ("remove", sid)


def test_delete_removes_priority_immediately(store, shaper, clock):
    sid = store.create(session_body())["sessionId"]
    store.tick(clock.advance(1.0))
    store.delete(sid)
    assert shaper.calls[-1] == ("remove", sid)
    assert store.changes[-1]["qosStatus"] == "UNAVAILABLE"
    assert store.changes[-1]["statusInfo"] == "DELETE_REQUESTED"


def test_second_session_same_device_conflict(store):
    store.create(session_body())
    with pytest.raises(ConflictError):
        store.create(session_body())


def test_new_session_allowed_after_expiry(store, clock):
    store.create(session_body())
    store.tick(clock.advance(1.0))
    store.tick(clock.advance(31))
    assert store.create(session_body())["qosStatus"] == "REQUESTED"


def test_duration_out_of_range(store):
    with pytest.raises(DurationOutOfRange):
        store.create(session_body(duration=2))


def test_extend_capped_by_max_duration(store, clock):
    sid = store.create(session_body(duration=3500))["sessionId"]
    store.tick(clock.advance(1.0))
    got = store.extend(sid, 500)
    assert got["duration"] == 3600
