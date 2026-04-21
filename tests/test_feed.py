import json
from datetime import date

from patristic_nectar_feed import (
    build_feed_xml,
    build_index_html,
    collection_name_for_date,
    fetch_synaxarion_entry,
    write_outputs,
    write_site_metadata,
)


def test_collection_name_for_date_uses_month_day_and_ordinal_suffix():
    assert collection_name_for_date(date(2026, 4, 19)) == "April 19th"
    assert collection_name_for_date(date(2026, 4, 1)) == "April 1st"
    assert collection_name_for_date(date(2026, 4, 2)) == "April 2nd"
    assert collection_name_for_date(date(2026, 4, 3)) == "April 3rd"
    assert collection_name_for_date(date(2026, 4, 11)) == "April 11th"


def test_fetch_synaxarion_entry_returns_audio_metadata_from_live_api():
    entry = fetch_synaxarion_entry(date(2026, 4, 19))

    assert entry["collection_name"] == "April 19th"
    assert entry["content_name"]
    assert "Matrona" in entry["content_name"] or "Paphnutios" in entry["content_name"]
    assert entry["audio_url"].startswith("https://")
    assert ".mp3" in entry["audio_url"]
    assert entry["mime"] == "audio/mpeg"
    assert entry["duration_seconds"] > 60


def test_build_feed_xml_includes_podcast_enclosure():
    entry = {
        "date": "2026-04-19",
        "collection_name": "April 19th",
        "content_id": 3478,
        "content_name": "Holy Hieromartyr Paphnutios, on the same day Blessed Matrona of Moscow",
        "content_slug": "holy-hieromartyr-paphnutios-on-the-same-day-blessed-matrona-of-moscow",
        "description_html": "<p>Holy Hieromartyr Paphnutios, on the same day Blessed Matrona of Moscow</p>",
        "image_url": "https://example.com/cover.jpg",
        "audio_url": "https://example.com/audio.mp3?token=abc",
        "audio_file_name": "example.mp3",
        "mime": "audio/mpeg",
        "audio_bytes": 123456,
        "duration_seconds": 426,
    }

    xml = build_feed_xml(
        [entry],
        site_url="https://app.patristicnectar.org/discover/synaxarion",
        feed_url="https://example.com/feed.xml",
        title="Patristic Nectar Synaxarion",
        description="Daily Synaxarion feed",
    )

    assert "<rss" in xml
    assert "<item>" in xml
    assert "Holy Hieromartyr Paphnutios" in xml
    assert '<enclosure url="https://example.com/audio.mp3?token=abc"' in xml
    assert 'type="audio/mpeg"' in xml
    assert '<itunes:duration>00:07:06</itunes:duration>' in xml
    assert '<itunes:type>episodic</itunes:type>' in xml
    assert '<itunes:image href="https://example.com/cover.jpg" />' in xml
    assert '<image>' in xml
    assert '<url>https://example.com/cover.jpg</url>' in xml


def test_build_feed_xml_includes_all_items_and_transcript_tags():
    entries = [
        {
            "date": "2026-04-20",
            "collection_name": "April 20th",
            "content_id": 3479,
            "content_name": "Righteous Father Theodore of the Hair-shirt",
            "content_slug": "righteous-father-theodore-of-the-hair-shirt",
            "description_html": "<p>Righteous Father Theodore of the Hair-shirt</p>",
            "image_url": "https://example.com/theodore.jpg",
            "audio_url": "https://example.com/theodore.mp3",
            "audio_file_name": "theodore.mp3",
            "mime": "audio/mpeg",
            "audio_bytes": 3468015,
            "duration_seconds": 87,
            "transcript_url": "https://example.com/transcripts/theodore.vtt",
            "transcript_mime": "text/vtt",
        },
        {
            "date": "2026-04-20",
            "collection_name": "April 20th",
            "content_id": 3483,
            "content_name": "Holy Apostle Zacchaeus",
            "content_slug": "holy-apostle-zacchaeus",
            "description_html": "<p>Holy Apostle Zacchaeus</p>",
            "image_url": "https://example.com/zacchaeus.jpg",
            "audio_url": "https://example.com/zacchaeus.mp3",
            "audio_file_name": "zacchaeus.mp3",
            "mime": "audio/mpeg",
            "audio_bytes": 2480000,
            "duration_seconds": 65,
            "transcript_url": "https://example.com/transcripts/zacchaeus.txt",
            "transcript_mime": "text/plain",
        },
    ]

    xml = build_feed_xml(
        entries,
        site_url="https://prbserver.tailae03c8.ts.net",
        feed_url="https://prbserver.tailae03c8.ts.net/feed.xml",
        title="Patristic Nectar Synaxarion",
        description="Daily Synaxarion feed",
    )

    assert xml.count("<item>") == 2
    assert "Righteous Father Theodore of the Hair-shirt" in xml
    assert "Holy Apostle Zacchaeus" in xml
    assert 'xmlns:podcast="https://podcastindex.org/namespace/1.0"' in xml
    assert '<podcast:transcript url="https://example.com/transcripts/theodore.vtt" type="text/vtt" />' in xml
    assert '<podcast:transcript url="https://example.com/transcripts/zacchaeus.txt" type="text/plain" />' in xml


def test_write_outputs_can_publish_multiple_self_hosted_audio_urls(tmp_path):
    entries = [
        {
            "date": "2026-04-20",
            "collection_name": "April 20th",
            "content_id": 3479,
            "content_name": "Righteous Father Theodore of the Hair-shirt",
            "content_slug": "righteous-father-theodore-of-the-hair-shirt",
            "description_html": "<p>Righteous Father Theodore of the Hair-shirt</p>",
            "image_url": "https://example.com/theodore.jpg",
            "audio_url": "https://remote.example.com/theodore.mp3?token=abc",
            "audio_file_name": "theodore-source.mp3",
            "mime": "audio/mpeg",
            "audio_bytes": 3468015,
            "duration_seconds": 87,
        },
        {
            "date": "2026-04-20",
            "collection_name": "April 20th",
            "content_id": 3483,
            "content_name": "Holy Apostle Zacchaeus",
            "content_slug": "holy-apostle-zacchaeus",
            "description_html": "<p>Holy Apostle Zacchaeus</p>",
            "image_url": "https://example.com/zacchaeus.jpg",
            "audio_url": "https://remote.example.com/zacchaeus.mp3?token=abc",
            "audio_file_name": "zacchaeus-source.mp3",
            "mime": "audio/mpeg",
            "audio_bytes": 2480000,
            "duration_seconds": 65,
        },
    ]

    json_path, xml_path = write_outputs(
        tmp_path,
        entries,
        feed_url="https://prbserver.tailae03c8.ts.net/feed.xml",
        public_base_url="https://prbserver.tailae03c8.ts.net",
    )

    saved_payload = json.loads(json_path.read_text())
    xml = xml_path.read_text()

    assert [entry["audio_url"] for entry in saved_payload["entries"]] == [
        "https://prbserver.tailae03c8.ts.net/audio/righteous-father-theodore-of-the-hair-shirt.mp3",
        "https://prbserver.tailae03c8.ts.net/audio/holy-apostle-zacchaeus.mp3",
    ]
    assert 'enclosure url="https://prbserver.tailae03c8.ts.net/audio/righteous-father-theodore-of-the-hair-shirt.mp3"' in xml
    assert 'enclosure url="https://prbserver.tailae03c8.ts.net/audio/holy-apostle-zacchaeus.mp3"' in xml
    assert xml.count("<item>") == 2


def test_write_site_metadata_writes_index_and_cname(tmp_path):
    entry = {
        "date": "2026-04-19",
        "collection_name": "April 19th",
        "content_id": 3478,
        "content_name": "Holy Hieromartyr Paphnutios, on the same day Blessed Matrona of Moscow",
        "content_slug": "holy-hieromartyr-paphnutios-on-the-same-day-blessed-matrona-of-moscow",
        "description_html": "<p>Holy Hieromartyr Paphnutios, on the same day Blessed Matrona of Moscow</p>",
        "image_url": "https://example.com/cover.jpg",
        "audio_url": "https://feed.knotandnous.com/audio/today.mp3",
        "audio_file_name": "today.mp3",
        "mime": "audio/mpeg",
        "audio_bytes": 123456,
        "duration_seconds": 426,
    }

    write_site_metadata(
        tmp_path,
        entry,
        feed_url="https://feed.knotandnous.com/feed.xml",
        custom_domain="feed.knotandnous.com",
    )

    assert (tmp_path / "CNAME").read_text().strip() == "feed.knotandnous.com"
    index_html = (tmp_path / "index.html").read_text()
    assert "Patristic Nectar Synaxarion Feed" in index_html
    assert "https://feed.knotandnous.com/feed.xml" in index_html
    assert "today.mp3" in index_html


def test_build_index_html_links_feed_and_latest_audio():
    entry = {
        "date": "2026-04-19",
        "content_name": "Holy Hieromartyr Paphnutios, on the same day Blessed Matrona of Moscow",
        "audio_url": "https://feed.knotandnous.com/audio/today.mp3",
        "duration_seconds": 426,
    }

    html = build_index_html(entry, feed_url="https://feed.knotandnous.com/feed.xml")

    assert "https://feed.knotandnous.com/feed.xml" in html
    assert "Holy Hieromartyr Paphnutios" in html
    assert "00:07:06" in html
