"""QoD oturumunu ağda uygulayan katman: net namespace'indeki tc HTB sınıfları."""
import subprocess
from typing import Protocol

PRIO_CLASS = "1:10"
DEFAULT_CLASS = "1:20"


class Shaper(Protocol):
    def add_priority(self, key: str, device_ip: str, server_ip: str, rate_kbps: int) -> None: ...
    def remove_priority(self, key: str) -> None: ...


class FakeShaper:
    """Testler için: yapılan çağrıları kaydeder."""

    def __init__(self):
        self.calls: list[tuple] = []

    def add_priority(self, key, device_ip, server_ip, rate_kbps):
        self.calls.append(("add", key, device_ip, server_ip, rate_kbps))

    def remove_priority(self, key):
        self.calls.append(("remove", key))


class TcShaper:
    """Darboğaz arayüzüne (net:n-srv) öncelikli bir HTB sınıfı ekler/kaldırır.

    Demoda tek cihaz olduğu için aynı anda tek öncelik sınıfı (1:10) vardır.
    """

    def __init__(self, ns: str = "net", dev: str = "n-srv", link_kbps: int = 3000):
        self.ns, self.dev, self.link_kbps = ns, dev, link_kbps
        self.active_key: str | None = None

    def _tc(self, *args: str, check: bool = True) -> None:
        subprocess.run(["ip", "netns", "exec", self.ns, "tc", *args], check=check,
                       capture_output=True, text=True)

    def _set_default_rate(self, kbps: int) -> None:
        self._tc("class", "change", "dev", self.dev, "parent", "1:1", "classid", DEFAULT_CLASS,
                 "htb", "rate", f"{kbps}kbit", "ceil", f"{self.link_kbps}kbit", "prio", "1")

    def add_priority(self, key, device_ip, server_ip, rate_kbps):
        if self.active_key is not None:
            self.remove_priority(self.active_key)
        rate = min(rate_kbps, self.link_kbps - 100)
        self._set_default_rate(self.link_kbps - rate)
        self._tc("class", "add", "dev", self.dev, "parent", "1:1", "classid", PRIO_CLASS,
                 "htb", "rate", f"{rate}kbit", "ceil", f"{self.link_kbps}kbit", "prio", "0")
        self._tc("qdisc", "add", "dev", self.dev, "parent", PRIO_CLASS, "handle", "10:",
                 "pfifo", "limit", "50")
        self._tc("filter", "add", "dev", self.dev, "parent", "1:", "protocol", "ip", "prio", "1",
                 "u32", "match", "ip", "src", f"{device_ip}/32", "match", "ip", "dst",
                 f"{server_ip}/32", "flowid", PRIO_CLASS)
        self.active_key = key

    def remove_priority(self, key):
        if key != self.active_key:
            return
        self._tc("filter", "del", "dev", self.dev, "parent", "1:", "prio", "1", check=False)
        self._tc("qdisc", "del", "dev", self.dev, "parent", PRIO_CLASS, "handle", "10:", check=False)
        self._tc("class", "del", "dev", self.dev, "classid", PRIO_CLASS, check=False)
        self._set_default_rate(self.link_kbps)
        self.active_key = None
