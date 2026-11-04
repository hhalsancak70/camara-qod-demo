import pytest
from qod.shaper import FakeShaper


class FakeClock:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> float:
        self.t += s
        return self.t


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def shaper():
    return FakeShaper()


def session_body(**over):
    body = {
        "device": {"ipv4Address": {"publicAddress": "10.10.1.2", "privateAddress": "10.10.1.2"}},
        "applicationServer": {"ipv4Address": "10.10.2.2"},
        "qosProfile": "QOS_VIDEO_L",
        "duration": 30,
    }
    body.update(over)
    return body
