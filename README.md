# Patristic Nectar Synaxarion Feed

Private/personal RSS feed generator for the daily Patristic Nectar Synaxarion, published as a static HTTPS site.

## What it does
- queries the Patristic Nectar GraphQL API for a given day's Synaxarion entry
- downloads the MP3 locally so the feed does not depend on expiring signed URLs
- emits a podcast-friendly `feed.xml`
- emits a simple `index.html`
- can emit a `CNAME` file for custom-domain hosting

## Local usage
```bash
./refresh_feed.sh
```

That regenerates `docs/` for the current live endpoint:
- `https://peterberthelsen.github.io/synaxarion/feed.xml`
- `https://peterberthelsen.github.io/synaxarion/audio/today.mp3`

## Publish to the live site
```bash
./publish_to_user_site.sh
```

That refreshes the feed locally, syncs `docs/` into the `PeterBerthelsen/peterberthelsen.github.io` repo under `/synaxarion/`, and pushes it live.

## Tests
```bash
pytest tests/ -q
```

## GitHub Pages deployment
The live feed is now published through the existing user site repo:
- site repo: `PeterBerthelsen/peterberthelsen.github.io`
- subpath: `/synaxarion/`

Expected public URLs:
- `https://peterberthelsen.github.io/synaxarion/feed.xml`
- `https://peterberthelsen.github.io/synaxarion/audio/today.mp3`

## Namecheap DNS
`feed.knotandnous.com` was attempted first but GitHub Pages TLS provisioning stalled. The active/public endpoint is currently the GitHub user-site URL above.
