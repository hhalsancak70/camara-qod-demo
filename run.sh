#!/usr/bin/env bash
# Demoyu başlatır: emüle ağ -> QoD servisi -> panel/alıcı -> edge göndericisi.
set -euo pipefail
cd "$(dirname "$0")"
./net/setup.sh
python -m qod.server --port 9091 > /tmp/qod.log 2>&1 &
python -m app.web --port 8080 &
WEB=$!
sleep 2
# Gönderici bağlantı koparsa kendiliğinden yeniden bağlanır.
( while true; do ip netns exec edge python -m media.sender >> /tmp/sender.log 2>&1; sleep 2; done ) &
echo "============================================================"
echo " Panel hazır:  http://localhost:8080"
echo " Pi'de:        http://<pi-adresi>:8080"
echo "============================================================"
wait $WEB
