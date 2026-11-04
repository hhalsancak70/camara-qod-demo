"""Gerçek tc ile: yalnızca emüle ağ kuruluyken (konteynerde net/setup.sh sonrası) çalışır."""
import os
import subprocess

import pytest

from qod.shaper import TcShaper

pytestmark = pytest.mark.skipif(not os.path.exists("/var/run/netns/net"), reason="emüle ağ kurulu değil")


def tc_show(what: str) -> str:
    return subprocess.run(["ip", "netns", "exec", "net", "tc", what, "show", "dev", "n-srv"],
                          capture_output=True, text=True, check=True).stdout


def test_priority_class_added_and_removed():
    s = TcShaper()
    s.add_priority("k1", "10.10.1.2", "10.10.2.2", 2500)
    assert "class htb 1:10" in tc_show("class")
    assert "flowid 1:10" in tc_show("filter")
    s.remove_priority("k1")
    assert "class htb 1:10" not in tc_show("class")
    assert "flowid 1:10" not in tc_show("filter")
    assert "rate 3Mbit" in [l for l in tc_show("class").splitlines() if "1:20" in l][0]
