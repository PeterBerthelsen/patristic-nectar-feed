#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/peter/automation/patristic-nectar-feed}"
OUTPUT_DIR="$PROJECT_DIR/docs"
TAILSCALE_BASE="https://prbserver.tailae03c8.ts.net"
FEED_URL="$TAILSCALE_BASE/feed.xml"
LOCAL_AUDIO_FILE_NAME="${LOCAL_AUDIO_FILE_NAME:-today.mp3}"
TARGET_DATE="${TARGET_DATE:-$(date +%F)}"

cd "$PROJECT_DIR"

OUTPUT_DIR="$OUTPUT_DIR" \
PUBLIC_BASE_URL="$TAILSCALE_BASE" \
FEED_URL="$FEED_URL" \
CUSTOM_DOMAIN="" \
LOCAL_AUDIO_FILE_NAME="$LOCAL_AUDIO_FILE_NAME" \
TARGET_DATE="$TARGET_DATE" \
./refresh_feed.sh >/tmp/patristic-nectar-refresh.json

# Restart server if not running (picks up new docs/)
OUTPUT_DIR="$OUTPUT_DIR" ./ensure_server.sh

echo "PUBLISHED $FEED_URL"
