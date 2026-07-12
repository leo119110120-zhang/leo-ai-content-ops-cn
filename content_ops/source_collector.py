from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen
from xml.etree import ElementTree

from content_ops.config import load_yaml, save_yaml


@dataclass(frozen=True)
class SourceRecord:
    id: str
    kind: str
    title: str
    content: str
    location: str
    retrieved_at: str
    sha256: str


def _local_record(
    path: Path,
    root: Path,
    kind: str,
    now: datetime,
    max_chars: int,
) -> SourceRecord:
    content = path.read_text(encoding="utf-8", errors="replace")
    digest = sha256(content.encode("utf-8")).hexdigest()
    return SourceRecord(
        id=f"src-{digest[:12]}",
        kind=kind,
        title=path.stem,
        content=content[:max_chars],
        location=path.relative_to(root).as_posix(),
        retrieved_at=now.isoformat(),
        sha256=digest,
    )


def _child_text(node, *names: str) -> str:
    for name in names:
        value = node.findtext(name)
        if value and value.strip():
            return value.strip()
    return ""


def _feed_records(
    feed_url: str,
    payload: bytes,
    now: datetime,
    max_chars: int,
) -> list[SourceRecord]:
    root = ElementTree.fromstring(payload)
    records: list[SourceRecord] = []
    for item in root.findall(".//item") + root.findall(".//{*}entry"):
        title = _child_text(item, "title", "{*}title") or "Untitled"
        link = _child_text(item, "link", "{*}link")
        if not link:
            link_node = item.find("{*}link")
            link = (
                link_node.get("href", "")
                if link_node is not None
                else ""
            )
        link = link or feed_url
        content = _child_text(
            item,
            "description",
            "{*}summary",
            "{*}content",
        ) or title
        digest = sha256((link + content).encode("utf-8")).hexdigest()
        records.append(
            SourceRecord(
                id=f"src-{digest[:12]}",
                kind="rss",
                title=title,
                content=content[:max_chars],
                location=link,
                retrieved_at=now.isoformat(),
                sha256=digest,
            )
        )
    return records


def _default_feed_fetcher(url: str) -> bytes:
    with urlopen(url, timeout=30) as response:
        return response.read()


def collect_sources(
    root: Path,
    state_dir: Path,
    now: datetime,
    feed_fetcher=None,
    max_items: int = 60,
    max_chars_per_item: int = 12000,
) -> list[SourceRecord]:
    cache_path = state_dir / "source-cache.yaml"
    cache = load_yaml(cache_path) if cache_path.exists() else {"seen": {}}
    seen = cache.setdefault("seen", {})

    paths: list[Path] = []
    wiki = root / "wiki"
    if wiki.exists():
        paths.extend(wiki.rglob("*.md"))
    raw_inbox = root / "raw" / "inbox"
    if raw_inbox.exists():
        paths.extend(path for path in raw_inbox.rglob("*") if path.is_file())
    backlog = root / "content-ops" / "topics" / "backlog.yaml"
    if backlog.exists():
        paths.append(backlog)

    changed: list[SourceRecord] = []
    for path in sorted(
        set(paths),
        key=lambda item: (item.stat().st_mtime, item.as_posix()),
        reverse=True,
    ):
        if path.is_relative_to(wiki):
            kind = "wiki"
        elif path.is_relative_to(raw_inbox):
            kind = "raw_inbox"
        else:
            kind = "backlog"
        record = _local_record(
            path, root, kind, now, max_chars_per_item
        )
        if seen.get(record.location) != record.sha256:
            changed.append(record)

    sources_config = root / "content-ops" / "config" / "sources.yaml"
    feed_urls = (
        load_yaml(sources_config).get("feeds", [])
        if sources_config.exists()
        else []
    )
    fetch = feed_fetcher or _default_feed_fetcher
    for feed_url in feed_urls:
        changed.extend(
            _feed_records(
                str(feed_url),
                fetch(str(feed_url)),
                now,
                max_chars_per_item,
            )
        )

    records: list[SourceRecord] = []
    for record in changed:
        if len(records) == max_items:
            break
        if seen.get(record.location) == record.sha256:
            continue
        records.append(record)
        seen[record.location] = record.sha256
    save_yaml(cache_path, cache)
    return records
