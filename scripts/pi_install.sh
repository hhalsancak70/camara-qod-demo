#!/usr/bin/env bash
# Raspberry Pi 5 (Raspberry Pi OS Lite 64-bit) üzerinde demoyu çalışmaya hazırlar.
# Bir kez çalıştırılır: Docker'ı kurar, gerekli çekirdek modüllerini yükler, imajı derler.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null; then
  echo ">> Docker kuruluyor (resmî kurulum betiği)..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

echo ">> Ağ emülasyonu için çekirdek modülleri yükleniyor..."
MODS="veth sch_htb sch_sfq sch_netem cls_u32"
for m in $MODS; do sudo modprobe "$m"; done
echo "$MODS" | tr ' ' '\n' | sudo tee /etc/modules-load.d/qod-demo.conf >/dev/null

echo ">> Demo imajı derleniyor (ilk seferde birkaç dakika sürer)..."
sudo docker compose build

echo ">> Hazır. Başlatmak için: sudo docker compose up -d"
echo ">> Panel: http://$(hostname).local:8080"
