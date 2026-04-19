#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/peter/automation/patristic-nectar-feed}"
OUTPUT_DIR="${OUTPUT_DIR:-$PROJECT_DIR/docs}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-https://feed.knotandnous.com}"
FEED_URL="${FEED_URL:-$PUBLIC_BASE_URL/feed.xml}"
CUSTOM_DOMAIN="${CUSTOM_DOMAIN:-feed.knotandnous.com}"
TARGET_DATE="${TARGET_DATE:-$(date +%F)}"
LOCAL_AUDIO_FILE_NAME="${LOCAL_AUDIO_FILE_NAME:-today.mp3}"

cd "$PROJECT_DIR"
rm -rf "$OUTPUT_DIR"
python patristic_nectar_feed.py \
  --date "$TARGET_DATE" \
  --output-dir "$OUTPUT_DIR" \
  --feed-url "$FEED_URL" \
  --public-base-url "$PUBLIC_BASE_URL" \
  --local-audio-file-name "$LOCAL_AUDIO_FILE_NAME" \
  --custom-domain "$CUSTOM_DOMAIN"
