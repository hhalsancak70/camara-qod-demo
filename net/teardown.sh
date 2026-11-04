#!/usr/bin/env bash
# Emüle ağı kaldırır. Hiçbiri yoksa sessizce geçer.
for ns in edge others net; do ip netns del "$ns" 2>/dev/null || true; done
ip link del s0 2>/dev/null || true
