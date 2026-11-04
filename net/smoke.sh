#!/usr/bin/env bash
# Ağın beklenen gibi olduğunu doğrular: RTT 45-60 ms, TCP verimi 2.6-3.1 Mbit/s.
set -uo pipefail
ip netns exec edge ping -c 1 10.10.2.2 >/dev/null  # ARP ısınması
rtt=$(ip netns exec edge ping -c 5 -i 0.2 10.10.2.2 | awk -F/ '/rtt|round-trip/ {print $5}')
iperf3 -s -B 10.10.2.3 -1 -D >/dev/null 2>&1; sleep 0.5
mbps=$(ip netns exec others iperf3 -c 10.10.2.3 -t 5 -J | python3 -c 'import json,sys; print(round(json.load(sys.stdin)["end"]["sum_received"]["bits_per_second"]/1e6,2))')
echo "rtt_ms=$rtt throughput_mbps=$mbps"
python3 - "$rtt" "$mbps" <<'PY'
import sys
rtt, mbps = float(sys.argv[1]), float(sys.argv[2])
ok = 45 <= rtt <= 60 and 2.6 <= mbps <= 3.1
print("SMOKE_OK" if ok else "SMOKE_FAIL"); sys.exit(0 if ok else 1)
PY
