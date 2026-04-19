from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import requests

API_URL = "https://api.patristicnectar.org/graphql"
DEFAULT_SITE_URL = "https://app.patristicnectar.org/discover/synaxarion"
USER_AGENT = "Basil Patristic Nectar Feed Prototype/0.1"


@dataclass
class SynaxarionEntry:
    date: str
    collection_name: str
    content_id: int
    content_name: str
    content_slug: str
    description_html: str
    image_url: str
    audio_url: str
    audio_file_name: str
    mime: str
    audio_bytes: int
    duration_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ordinal(day: int) -> str:
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def collection_name_for_date(target_date: date) -> str:
    return f"{target_date.strftime('%B')} {ordinal(target_date.day)}"


def graphql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.post(
        API_URL,
        json={"query": query, "variables": variables or {}},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


def fetch_synaxarion_entry(target_date: date) -> dict[str, Any]:
    collection_name = collection_name_for_date(target_date)
    collection_data = graphql(
        """
        query($filter: CollectionFilterArgs){
          allCollections(filter:$filter){
            id
            name
            slug
            description
          }
        }
        """,
        {"filter": {"name": {"_eq": collection_name}}},
    )
    collections = collection_data["allCollections"]
    if not collections:
        raise LookupError(f"No Synaxarion collection found for {collection_name}")
    collection = collections[0]

    item_data = graphql(
        """
        query($parentId:ID!){
          allCollectionItems(parentId:$parentId, displayMode:SERIES){
            item {
              __typename
              ... on Content {
                id
                name
                slug
                description
                asset { id type duration }
                cover { src }
              }
            }
          }
        }
        """,
        {"parentId": str(collection["id"])}
    )
    items = item_data["allCollectionItems"]
    content = next((item["item"] for item in items if item["item"]["__typename"] == "Content"), None)
    if not content:
        raise LookupError(f"No content item found for {collection_name}")

    file_data = graphql(
        """
        query($id:ID!){
          File(id:$id){
            name
            src
            mime
            duration
          }
        }
        """,
        {"id": str(content["asset"]["id"])}
    )["File"]

    audio_url = file_data["src"]
    audio_bytes = content_length_for_url(audio_url)
    duration_data = file_data.get("duration") or content["asset"].get("duration") or {}

    entry = SynaxarionEntry(
        date=target_date.isoformat(),
        collection_name=collection_name,
        content_id=int(content["id"]),
        content_name=content["name"],
        content_slug=content["slug"],
        description_html=content["description"] or "",
        image_url=(content.get("cover") or {}).get("src", ""),
        audio_url=audio_url,
        audio_file_name=file_data["name"],
        mime=file_data["mime"],
        audio_bytes=audio_bytes,
        duration_seconds=round((duration_data or {}).get("length", 0)),
    )
    return entry.to_dict()


def content_length_for_url(url: str) -> int:
    response = requests.head(url, headers={"User-Agent": USER_AGENT}, allow_redirects=True, timeout=30)
    if response.ok and response.headers.get("content-length"):
        return int(response.headers["content-length"])
    fallback = requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=30)
    fallback.raise_for_status()
    if fallback.headers.get("content-length"):
        return int(fallback.headers["content-length"])
    total = 0
    for chunk in fallback.iter_content(chunk_size=1024 * 1024):
        total += len(chunk)
        if total > 0:
            break
    return total


def format_duration(total_seconds: int) -> str:
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def strip_html_paragraphs(html: str) -> str:
    return (
        html.replace("<p>", "")
        .replace("</p>", "")
        .replace("<br>", "\n")
        .replace("<br/>", "\n")
        .replace("<br />", "\n")
        .strip()
    )


def build_index_html(entry: dict[str, Any], *, feed_url: str) -> str:
    title = "Patristic Nectar Synaxarion Feed"
    episode_name = escape(entry["content_name"])
    audio_url = escape(entry["audio_url"])
    duration = format_duration(int(entry["duration_seconds"]))
    entry_date = escape(entry["date"])
    escaped_feed_url = escape(feed_url)
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 2rem auto; max-width: 760px; padding: 0 1rem; line-height: 1.5; color: #222; }}
      code, a.button {{ background: #f5f5f5; border-radius: 6px; padding: 0.15rem 0.35rem; }}
      a.button {{ text-decoration: none; display: inline-block; margin-right: 0.75rem; }}
      .meta {{ color: #666; }}
    </style>
  </head>
  <body>
    <h1>{title}</h1>
    <p>Private podcast feed generated from the daily Patristic Nectar Synaxarion.</p>
    <p><a class="button" href="{escaped_feed_url}">Open RSS feed</a><a class="button" href="{audio_url}">Play latest MP3</a></p>
    <h2>Latest episode</h2>
    <p><strong>{episode_name}</strong></p>
    <p class="meta">Date: {entry_date} · Duration: {duration}</p>
    <p>Feed URL: <code>{escaped_feed_url}</code></p>
  </body>
</html>
"""


def write_site_metadata(
    output_dir: Path,
    entry: dict[str, Any],
    *,
    feed_url: str,
    custom_domain: str | None = None,
) -> None:
    (output_dir / "index.html").write_text(
        build_index_html(entry, feed_url=feed_url) + "\n",
        encoding="utf-8",
    )
    if custom_domain:
        (output_dir / "CNAME").write_text(custom_domain.strip() + "\n", encoding="utf-8")


def build_feed_xml(
    entries: list[dict[str, Any]],
    *,
    site_url: str,
    feed_url: str,
    title: str,
    description: str,
) -> str:
    last_build = format_datetime(datetime.now(timezone.utc))
    items_xml = []
    for entry in entries:
        pub_date = format_datetime(
            datetime.fromisoformat(entry["date"] + "T06:00:00+00:00")
        )
        summary = escape(strip_html_paragraphs(entry.get("description_html", "")))
        item = f"""
    <item>
      <title>{escape(entry['content_name'])}</title>
      <guid isPermaLink="false">patristic-nectar:{entry['content_id']}</guid>
      <link>{escape(site_url)}?date={entry['date']}</link>
      <pubDate>{pub_date}</pubDate>
      <description>{summary}</description>
      <itunes:summary>{summary}</itunes:summary>
      <itunes:image href="{escape(entry['image_url'])}" />
      <enclosure url="{escape(entry['audio_url'])}" length="{entry['audio_bytes']}" type="{escape(entry['mime'])}" />
      <itunes:duration>{format_duration(int(entry['duration_seconds']))}</itunes:duration>
    </item>""".strip()
        items_xml.append(item)

    joined_items = "\n    ".join(items_xml)
    first_image = escape(entries[0]["image_url"]) if entries else ""
    channel_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
  xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(title)}</title>
    <link>{escape(site_url)}</link>
    <description>{escape(description)}</description>
    <language>en-us</language>
    <lastBuildDate>{last_build}</lastBuildDate>
    <atom:link href="{escape(feed_url)}" rel="self" type="application/rss+xml" />
    <itunes:author>Patristic Nectar Publications</itunes:author>
    <itunes:summary>{escape(description)}</itunes:summary>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <itunes:category text="Religion &amp; Spirituality">
      <itunes:category text="Christianity" />
    </itunes:category>
    <itunes:image href="{first_image}" />
    <image>
      <url>{first_image}</url>
      <title>{escape(title)}</title>
      <link>{escape(site_url)}</link>
    </image>
    {joined_items}
  </channel>
</rss>
"""
    return channel_xml


def self_hosted_audio_url(public_base_url: str, local_audio_file_name: str) -> str:
    return f"{public_base_url.rstrip('/')}/audio/{local_audio_file_name.lstrip('/')}"


def with_self_hosted_audio_url(
    entry: dict[str, Any],
    *,
    public_base_url: str,
    local_audio_file_name: str,
) -> dict[str, Any]:
    hosted_entry = dict(entry)
    hosted_entry["source_audio_url"] = entry["audio_url"]
    hosted_entry["audio_url"] = self_hosted_audio_url(public_base_url, local_audio_file_name)
    hosted_entry["audio_file_name"] = local_audio_file_name
    return hosted_entry


def download_audio_file(source_url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(source_url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=60) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
    return destination


def write_outputs(
    output_dir: Path,
    entry: dict[str, Any],
    *,
    feed_url: str,
    public_base_url: str | None = None,
    local_audio_file_name: str | None = None,
    custom_domain: str | None = None,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered_entry = dict(entry)
    if public_base_url and local_audio_file_name:
        rendered_entry = with_self_hosted_audio_url(
            entry,
            public_base_url=public_base_url,
            local_audio_file_name=local_audio_file_name,
        )
    json_path = output_dir / "today.json"
    xml_path = output_dir / "feed.xml"
    json_path.write_text(json.dumps(rendered_entry, indent=2) + "\n", encoding="utf-8")
    site_url = public_base_url.rstrip("/") if public_base_url else DEFAULT_SITE_URL
    xml_path.write_text(
        build_feed_xml(
            [rendered_entry],
            site_url=site_url,
            feed_url=feed_url,
            title="Patristic Nectar Synaxarion",
            description="Daily Synaxarion audio from Patristic Nectar, reformatted into a private podcast feed.",
        ),
        encoding="utf-8",
    )
    write_site_metadata(output_dir, rendered_entry, feed_url=feed_url, custom_domain=custom_domain)
    return json_path, xml_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a private Patristic Nectar Synaxarion feed artifact.")
    parser.add_argument("--date", default=date.today().isoformat(), help="Target date in YYYY-MM-DD form")
    parser.add_argument("--output-dir", default="output", help="Directory where today.json and feed.xml will be written")
    parser.add_argument("--feed-url", default="https://example.com/feed.xml", help="Public URL where the resulting feed.xml will be hosted")
    parser.add_argument("--public-base-url", help="Base URL where the output directory is served, used for self-hosted audio enclosure URLs")
    parser.add_argument("--local-audio-file-name", default="today.mp3", help="Local file name to use when self-hosting the downloaded audio")
    parser.add_argument("--custom-domain", help="Optional custom domain to write into a CNAME file for static hosting")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date)
    entry = fetch_synaxarion_entry(target_date)
    output_dir = Path(args.output_dir)
    if args.public_base_url:
        download_audio_file(entry["audio_url"], output_dir / "audio" / args.local_audio_file_name)
    json_path, xml_path = write_outputs(
        output_dir,
        entry,
        feed_url=args.feed_url,
        public_base_url=args.public_base_url,
        local_audio_file_name=args.local_audio_file_name if args.public_base_url else None,
        custom_domain=args.custom_domain,
    )
    print(json.dumps({"json_path": str(json_path), "xml_path": str(xml_path), "entry": entry}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
