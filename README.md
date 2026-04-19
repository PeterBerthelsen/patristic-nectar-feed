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

That regenerates `docs/` with:
- `feed.xml`
- `audio/today.mp3`
- `index.html`
- `CNAME`

## Tests
```bash
pytest tests/ -q
```

## GitHub Pages deployment
This repo is set up for **GitHub Pages from the `main` branch `/docs` folder**.

Typical publish flow:
1. run `./refresh_feed.sh`
2. commit the updated `docs/` artifacts
3. push to `main`
4. GitHub Pages serves the updated feed on the custom domain

Expected public URLs:
- `https://feed.knotandnous.com/feed.xml`
- `https://feed.knotandnous.com/audio/today.mp3`

## Namecheap DNS
For `feed.knotandnous.com`, create a `CNAME` record:
- Host: `feed`
- Value: `PeterBerthelsen.github.io`
- TTL: `Automatic`

If Namecheap shows a "proxy" option, leave it off. GitHub Pages should answer directly.
