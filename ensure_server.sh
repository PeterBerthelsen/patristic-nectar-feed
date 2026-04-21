#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="${OUTPUT_DIR:-/home/peter/automation/patristic-nectar-feed/docs}"
PORT="8019"
LOG_FILE="/tmp/patristic-nectar-http.log"

if ss -ltn sport = :$PORT | grep -q LISTEN; then
  exit 0
fi

cd "$OUTPUT_DIR"
nohup python3 -m http.server "$PORT" -b 127.0.0.1 -d "$OUTPUT_DIR" >> "$LOG_FILE" 2>&1 &
