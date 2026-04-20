#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/peter/automation/patristic-nectar-feed}"
SITE_REPO_DIR="${SITE_REPO_DIR:-/home/peter/automation/peterberthelsen.github.io}"
SITE_REPO_URL="${SITE_REPO_URL:-https://github.com/PeterBerthelsen/peterberthelsen.github.io.git}"
TARGET_SUBDIR="${TARGET_SUBDIR:-synaxarion}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-https://peterberthelsen.github.io/${TARGET_SUBDIR}}"
FEED_URL="${FEED_URL:-${PUBLIC_BASE_URL}/feed.xml}"
LOCAL_AUDIO_FILE_NAME="${LOCAL_AUDIO_FILE_NAME:-today.mp3}"
TARGET_DATE="${TARGET_DATE:-$(date +%F)}"

if [ ! -d "$SITE_REPO_DIR/.git" ]; then
  mkdir -p "$(dirname "$SITE_REPO_DIR")"
  git clone "$SITE_REPO_URL" "$SITE_REPO_DIR"
fi

git -C "$SITE_REPO_DIR" pull --ff-only origin master
git -C "$SITE_REPO_DIR" config user.name "Peter Berthelsen"
git -C "$SITE_REPO_DIR" config user.email "PeterBerthelsen@users.noreply.github.com"

cd "$PROJECT_DIR"
OUTPUT_DIR="$PROJECT_DIR/docs" \
PUBLIC_BASE_URL="$PUBLIC_BASE_URL" \
FEED_URL="$FEED_URL" \
CUSTOM_DOMAIN="" \
LOCAL_AUDIO_FILE_NAME="$LOCAL_AUDIO_FILE_NAME" \
TARGET_DATE="$TARGET_DATE" \
./refresh_feed.sh >/tmp/patristic-nectar-refresh.json

mkdir -p "$SITE_REPO_DIR/$TARGET_SUBDIR"
rsync -a --delete "$PROJECT_DIR/docs/" "$SITE_REPO_DIR/$TARGET_SUBDIR/"

cd "$SITE_REPO_DIR"
if [ -n "$(git status --porcelain -- "$TARGET_SUBDIR")" ]; then
  git add "$TARGET_SUBDIR"
  git commit -m "Publish Synaxarion feed for $TARGET_DATE"
  git push origin master
  echo "PUBLISHED $FEED_URL"
else
  echo "NO_CHANGES $FEED_URL"
fi
