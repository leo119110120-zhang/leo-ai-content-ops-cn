import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from content_ops.source_collector import collect_sources


class SourceCollectorTests(unittest.TestCase):
    def test_collects_local_inputs_without_modifying_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "wiki").mkdir()
            (root / "raw" / "inbox").mkdir(parents=True)
            (root / "content-ops" / "topics").mkdir(parents=True)
            (root / "wiki" / "note.md").write_text(
                "用户反复询问自动化成本", encoding="utf-8"
            )
            raw = root / "raw" / "inbox" / "idea.txt"
            raw.write_text("评论区都在问如何部署", encoding="utf-8")
            (root / "content-ops" / "topics" / "backlog.yaml").write_text(
                "topics: []\n", encoding="utf-8"
            )
            before = hashlib.sha256(raw.read_bytes()).hexdigest()

            records = collect_sources(
                root,
                root / "content-ops" / "state",
                datetime(2026, 7, 13, 2, 30, tzinfo=timezone.utc),
            )

            self.assertEqual(
                {record.kind for record in records},
                {"wiki", "raw_inbox", "backlog"},
            )
            self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(), before)

    def test_unchanged_content_is_not_returned_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "wiki").mkdir()
            (root / "raw" / "inbox").mkdir(parents=True)
            (root / "content-ops" / "topics").mkdir(parents=True)
            (root / "wiki" / "note.md").write_text(
                "同一份内容", encoding="utf-8"
            )
            (root / "content-ops" / "topics" / "backlog.yaml").write_text(
                "topics: []\n", encoding="utf-8"
            )
            state = root / "content-ops" / "state"
            now = datetime(2026, 7, 13, 2, 30, tzinfo=timezone.utc)

            first = collect_sources(root, state, now)
            second = collect_sources(root, state, now)

            self.assertGreater(len(first), 0)
            self.assertEqual(second, [])

    def test_allowlisted_rss_is_parsed_without_browser_or_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "wiki").mkdir()
            (root / "raw" / "inbox").mkdir(parents=True)
            (root / "content-ops" / "topics").mkdir(parents=True)
            (root / "content-ops" / "config").mkdir(parents=True)
            (root / "content-ops" / "topics" / "backlog.yaml").write_text(
                "topics: []\n", encoding="utf-8"
            )
            (root / "content-ops" / "config" / "sources.yaml").write_text(
                "feeds:\n  - https://example.com/feed.xml\n",
                encoding="utf-8",
            )
            xml = (
                b'<?xml version="1.0"?><rss><channel><item>'
                b"<title>AI update</title>"
                b"<link>https://example.com/a</link>"
                b"<description>Official change</description>"
                b"</item></channel></rss>"
            )

            records = collect_sources(
                root,
                root / "content-ops" / "state",
                datetime(2026, 7, 13, 2, 30, tzinfo=timezone.utc),
                feed_fetcher=lambda url: xml,
            )

            rss = [record for record in records if record.kind == "rss"]
            self.assertEqual(rss[0].location, "https://example.com/a")
            self.assertEqual(rss[0].title, "AI update")

    def test_max_items_pages_unseen_sources_without_losing_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "wiki").mkdir()
            for index in range(3):
                (root / "wiki" / f"note-{index}.md").write_text(
                    f"内容 {index}", encoding="utf-8"
                )
            state = root / "content-ops" / "state"
            now = datetime(2026, 7, 13, 2, 30, tzinfo=timezone.utc)

            first = collect_sources(root, state, now, max_items=2)
            second = collect_sources(root, state, now, max_items=2)

            self.assertEqual(len(first), 2)
            self.assertEqual(len(second), 1)
            self.assertTrue({item.id for item in first}.isdisjoint(
                {item.id for item in second}
            ))
