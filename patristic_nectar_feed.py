from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import requests

API_URL = "https://api.patristicnectar.org/graphql"
DEFAULT_SITE_URL = "https://app.patristicnectar.org/discover/synaxarion"
USER_AGENT = "Basil Patristic Nectar Feed Prototype/0.1"
PODCAST_NAMESPACE = "https://podcastindex.org/namespace/1.0"
_DEFAULT_TRANSCRIPT_MODEL = os.getenv("PATRISTIC_TRANSCRIPT_MODEL", "base")
_DEFAULT_TRANSCRIPT_DEVICE = os.getenv("PATRISTIC_TRANSCRIPT_DEVICE", "cpu")
_DEFAULT_TRANSCRIPT_COMPUTE_TYPE = os.getenv("PATRISTIC_TRANSCRIPT_COMPUTE_TYPE", "int8")
_whisper_model = None


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
    transcript_url: str | None = None
    transcript_mime: str | None = None
    local_transcript_file_name: str | None = None

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


def fetch_synaxarion_entries(target_date: date) -> list[dict[str, Any]]:
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
    contents = [item["item"] for item in items if item["item"]["__typename"] == "Content"]
    if not contents:
        raise LookupError(f"No content items found for {collection_name}")

    entries: list[dict[str, Any]] = []
    for content in contents:
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
        entries.append(entry.to_dict())
    return entries


def fetch_synaxarion_entry(target_date: date) -> dict[str, Any]:
    return fetch_synaxarion_entries(target_date)[0]


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


def build_output_manifest(entries: list[dict[str, Any]]) -> dict[str, Any]:
    first = entries[0] if entries else {}
    return {
        "date": first.get("date"),
        "collection_name": first.get("collection_name"),
        "entry_count": len(entries),
        "entries": entries,
    }


def build_index_html(entry_or_entries: dict[str, Any] | list[dict[str, Any]], *, feed_url: str) -> str:
    entries = entry_or_entries if isinstance(entry_or_entries, list) else [entry_or_entries]
    latest = entries[0]
    title = "Patristic Nectar Synaxarion Feed"
    escaped_feed_url = escape(feed_url)
    latest_audio_url = escape(latest["audio_url"])
    latest_duration = format_duration(int(latest["duration_seconds"]))
    latest_date = escape(latest["date"])
    episode_items = "\n".join(
        f'      <li><strong>{escape(entry["content_name"])}</strong> '
        f'<span class="meta">({format_duration(int(entry["duration_seconds"]))})</span> '
        f'<a href="{escape(entry["audio_url"])}">MP3</a></li>'
        for entry in entries
    )
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
    <p><a class="button" href="{escaped_feed_url}">Open RSS feed</a><a class="button" href="{latest_audio_url}">Play latest MP3</a></p>
    <h2>Latest drop</h2>
    <p><strong>{escape(latest['content_name'])}</strong></p>
    <p class="meta">Date: {latest_date} · Duration: {latest_duration}</p>
    <h2>Episodes in this collection</h2>
    <ul>
{episode_items}
    </ul>
    <p>Feed URL: <code>{escaped_feed_url}</code></p>
  </body>
</html>
"""


def write_site_metadata(
    output_dir: Path,
    entry_or_entries: dict[str, Any] | list[dict[str, Any]],
    *,
    feed_url: str,
    custom_domain: str | None = None,
) -> None:
    (output_dir / "index.html").write_text(
        build_index_html(entry_or_entries, feed_url=feed_url) + "\n",
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
    for index, entry in enumerate(entries):
        pub_date = format_datetime(
            datetime.fromisoformat(entry["date"] + "T06:00:00+00:00") + timedelta(minutes=index)
        )
        summary = escape(strip_html_paragraphs(entry.get("description_html", "")))
        transcript_xml = ""
        if entry.get("transcript_url") and entry.get("transcript_mime"):
            transcript_xml = (
                f'\n      <podcast:transcript url="{escape(entry["transcript_url"])}" '
                f'type="{escape(entry["transcript_mime"])}" />'
            )
        item = f"""
    <item>
      <title>{escape(entry['content_name'])}</title>
      <guid isPermaLink="false">patristic-nectar:{entry['content_id']}</guid>
      <link>{escape(site_url)}?date={entry['date']}&amp;episode={escape(entry['content_slug'])}</link>
      <pubDate>{pub_date}</pubDate>
      <description>{summary}</description>
      <itunes:summary>{summary}</itunes:summary>
      <itunes:image href="{escape(entry['image_url'])}" />
      <enclosure url="{escape(entry['audio_url'])}" length="{entry['audio_bytes']}" type="{escape(entry['mime'])}" />
      <itunes:duration>{format_duration(int(entry['duration_seconds']))}</itunes:duration>{transcript_xml}
    </item>""".strip()
        items_xml.append(item)

    joined_items = "\n    ".join(items_xml)
    first_image = escape(entries[0]["image_url"]) if entries else ""
    channel_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:podcast="{PODCAST_NAMESPACE}">
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


def self_hosted_transcript_url(public_base_url: str, local_transcript_file_name: str) -> str:
    return f"{public_base_url.rstrip('/')}/transcripts/{local_transcript_file_name.lstrip('/')}"


def media_suffix(entry: dict[str, Any]) -> str:
    suffix = Path(entry.get("audio_file_name") or "").suffix.lower()
    if suffix:
        return suffix
    mime = (entry.get("mime") or "").lower()
    if mime == "audio/mpeg":
        return ".mp3"
    if mime == "audio/mp4":
        return ".m4a"
    return ".bin"


def local_audio_file_name_for_entry(entry: dict[str, Any], *, override: str | None = None) -> str:
    if override:
        return override
    return f"{entry['content_slug']}{media_suffix(entry)}"


def with_self_hosted_media_urls(
    entry: dict[str, Any],
    *,
    public_base_url: str,
    local_audio_file_name: str,
) -> dict[str, Any]:
    hosted_entry = dict(entry)
    hosted_entry["source_audio_url"] = entry["audio_url"]
    hosted_entry["audio_url"] = self_hosted_audio_url(public_base_url, local_audio_file_name)
    hosted_entry["audio_file_name"] = local_audio_file_name
    transcript_file_name = hosted_entry.get("local_transcript_file_name")
    if transcript_file_name:
        hosted_entry["transcript_url"] = self_hosted_transcript_url(public_base_url, transcript_file_name)
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


def _load_whisper_model():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    from faster_whisper import WhisperModel

    try:
        _whisper_model = WhisperModel(
            _DEFAULT_TRANSCRIPT_MODEL,
            device=_DEFAULT_TRANSCRIPT_DEVICE,
            compute_type=_DEFAULT_TRANSCRIPT_COMPUTE_TYPE,
        )
    except Exception:
        _whisper_model = WhisperModel(
            _DEFAULT_TRANSCRIPT_MODEL,
            device="cpu",
            compute_type="int8",
        )
    return _whisper_model


def _format_vtt_timestamp(seconds: float) -> str:
    total_milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def generate_transcript_files(audio_path: Path, transcript_base_path: Path) -> dict[str, Any] | None:
    try:
        model = _load_whisper_model()
        segments, _info = model.transcribe(str(audio_path), beam_size=5, vad_filter=True)
        segment_list = list(segments)
        if not segment_list:
            return None
    except Exception as exc:
        print(f"warning: transcript generation skipped for {audio_path.name}: {exc}")
        return None

    transcript_base_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path = transcript_base_path.with_suffix(".txt")
    vtt_path = transcript_base_path.with_suffix(".vtt")

    txt_lines = [segment.text.strip() for segment in segment_list if segment.text.strip()]
    txt_path.write_text("\n".join(txt_lines).strip() + "\n", encoding="utf-8")

    vtt_lines = ["WEBVTT", ""]
    for segment in segment_list:
        text = segment.text.strip()
        if not text:
            continue
        vtt_lines.extend(
            [
                f"{_format_vtt_timestamp(segment.start)} --> {_format_vtt_timestamp(segment.end)}",
                text,
                "",
            ]
        )
    vtt_path.write_text("\n".join(vtt_lines).rstrip() + "\n", encoding="utf-8")

    return {
        "local_transcript_file_name": vtt_path.name,
        "transcript_mime": "text/vtt",
        "transcript_text_file_name": txt_path.name,
    }


def write_outputs(
    output_dir: Path,
    entry_or_entries: dict[str, Any] | list[dict[str, Any]],
    *,
    feed_url: str,
    public_base_url: str | None = None,
    local_audio_file_name: str | None = None,
    custom_domain: str | None = None,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_entries = entry_or_entries if isinstance(entry_or_entries, list) else [entry_or_entries]
    rendered_entries: list[dict[str, Any]] = []
    for index, entry in enumerate(raw_entries):
        rendered_entry = dict(entry)
        if public_base_url:
            rendered_entry = with_self_hosted_media_urls(
                entry,
                public_base_url=public_base_url,
                local_audio_file_name=local_audio_file_name_for_entry(
                    entry,
                    override=local_audio_file_name if len(raw_entries) == 1 and index == 0 else None,
                ),
            )
        rendered_entries.append(rendered_entry)

    json_path = output_dir / "today.json"
    xml_path = output_dir / "feed.xml"
    manifest = build_output_manifest(rendered_entries)
    json_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    site_url = public_base_url.rstrip("/") if public_base_url else DEFAULT_SITE_URL
    xml_path.write_text(
        build_feed_xml(
            rendered_entries,
            site_url=site_url,
            feed_url=feed_url,
            title="Patristic Nectar Synaxarion",
            description="Daily Synaxarion audio from Patristic Nectar, reformatted into a private podcast feed.",
        ),
        encoding="utf-8",
    )
    write_site_metadata(output_dir, rendered_entries, feed_url=feed_url, custom_domain=custom_domain)
    return json_path, xml_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a private Patristic Nectar Synaxarion feed artifact.")
    parser.add_argument("--date", default=date.today().isoformat(), help="Target date in YYYY-MM-DD form")
    parser.add_argument("--output-dir", default="output", help="Directory where today.json and feed.xml will be written")
    parser.add_argument("--feed-url", default="https://example.com/feed.xml", help="Public URL where the resulting feed.xml will be hosted")
    parser.add_argument("--public-base-url", help="Base URL where the output directory is served, used for self-hosted audio enclosure URLs")
    parser.add_argument("--local-audio-file-name", default="today.mp3", help="Override local file name when the collection only has one audio item")
    parser.add_argument("--custom-domain", help="Optional custom domain to write into a CNAME file for static hosting")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date)
    entries = fetch_synaxarion_entries(target_date)
    output_dir = Path(args.output_dir)
    if args.public_base_url:
        for index, entry in enumerate(entries):
            local_audio_file_name = local_audio_file_name_for_entry(
                entry,
                override=args.local_audio_file_name if len(entries) == 1 and index == 0 else None,
            )
            audio_path = download_audio_file(entry["audio_url"], output_dir / "audio" / local_audio_file_name)
            transcript_info = generate_transcript_files(
                audio_path,
                output_dir / "transcripts" / entry["content_slug"],
            )
            if transcript_info:
                entry.update(transcript_info)
    json_path, xml_path = write_outputs(
        output_dir,
        entries,
        feed_url=args.feed_url,
        public_base_url=args.public_base_url,
        local_audio_file_name=args.local_audio_file_name if len(entries) == 1 and args.public_base_url else None,
        custom_domain=args.custom_domain,
    )
    print(json.dumps({"json_path": str(json_path), "xml_path": str(xml_path), "entry_count": len(entries), "entries": entries}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
