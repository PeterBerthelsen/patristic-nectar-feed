#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="/mnt/c/Users/peter/iCloudDrive/iCloud~md~obsidian/Agents-HQ/00 Inbox/patristic-nectar-synaxarion"
PORT="8019"
LOG_FILE="$OUTPUT_DIR/http-server.log"

if ss -ltn sport = :$PORT | grep -q LISTEN; then
  exit 0
fi

cd "$OUTPUT_DIR"
nohup python -m http.server "$PORT" --bind 0.0.0.0 >> "$LOG_FILE" 2>&1 &
