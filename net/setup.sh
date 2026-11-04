#!/usr/bin/env bash
# Emüle mobil ağı kurar: edge/others -> net (darboğaz) -> kök (sunucu).
# Her çalıştırmada önce eskisini siler, böylece kalıntı tc sınıfı kalmaz.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
LINK_KBIT="${LINK_KBIT:-3000}"
RTT_MS="${RTT_MS:-50}"
"$DIR/teardown.sh"

for ns in edge others net; do ip netns add "$ns"; done
ip link add e0 netns edge type veth peer name n-edge netns net
ip link add o0 netns others type veth peer name n-oth netns net
ip link add n-srv netns net type veth peer name s0

ip -n edge   addr add 10.10.1.2/24 dev e0
ip -n others addr add 10.10.3.2/24 dev o0
ip -n net    addr add 10.10.1.1/24 dev n-edge
ip -n net    addr add 10.10.3.1/24 dev n-oth
ip -n net    addr add 10.10.2.1/24 dev n-srv
ip addr add 10.10.2.2/24 dev s0
ip addr add 10.10.2.3/24 dev s0

for ns in edge others net; do ip -n "$ns" link set lo up; done
ip -n edge link set e0 up; ip -n others link set o0 up
for d in n-edge n-oth n-srv; do ip -n net link set "$d" up; done
ip link set s0 up

ip netns exec net sysctl -qw net.ipv4.ip_forward=1
ip -n edge   route add default via 10.10.1.1
ip -n others route add default via 10.10.3.1
ip route add 10.10.1.0/24 via 10.10.2.1 dev s0
ip route add 10.10.3.0/24 via 10.10.2.1 dev s0

# Büyük birleşik paketler kuyruğu ve ölçümü bozmasın.
for d in e0:edge o0:others n-edge:net n-oth:net n-srv:net; do
  ip netns exec "${d#*:}" ethtool -K "${d%%:*}" tso off gso off gro off >/dev/null 2>&1 || true
done
ethtool -K s0 tso off gso off gro off >/dev/null 2>&1 || true

# Uplink darboğazı: n-srv çıkışı. 1:20 varsayılan (best effort) sınıf, büyük kuyruk.
ip netns exec net tc qdisc add dev n-srv root handle 1: htb default 20
ip netns exec net tc class add dev n-srv parent 1: classid 1:1 htb rate ${LINK_KBIT}kbit ceil ${LINK_KBIT}kbit
ip netns exec net tc class add dev n-srv parent 1:1 classid 1:20 htb rate ${LINK_KBIT}kbit ceil ${LINK_KBIT}kbit prio 1
ip netns exec net tc qdisc add dev n-srv parent 1:20 handle 20: pfifo limit 400

# RTT: yalnızca dönüş yolunda gecikme.
ip netns exec net tc qdisc add dev n-edge root netem delay ${RTT_MS}ms
ip netns exec net tc qdisc add dev n-oth  root netem delay ${RTT_MS}ms
echo "NET_READY link=${LINK_KBIT}kbit rtt=${RTT_MS}ms"
