import hashlib
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from sqlalchemy import select, text

from .editorial import active_config
from .models import (
    Document,
    DocumentVersion,
    Event,
    IngestRun,
    Mention,
    Observation,
    Source,
    TrendSample,
)
from .network import FetchError, check_robots, fetch
from .schemas import DocumentInput

STOPWORDS = set(
    "de la el en los las del un una por para con que al se y a o su sus es como más ante tras sobre".split()
)


def tokens(value: str) -> set[str]:
    value = "".join(
        c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c)
    )
    return {word for word in re.findall(r"\w+", value) if len(word) > 2 and word not in STOPWORDS}


def canonical_url(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("URL inválida")
    query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid")
    ]
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or "/",
            urlencode(sorted(query)),
            "",
        )
    )


def plain(value: str) -> str:
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)


def parse_date(value: str | None) -> float | None:
    if not value:
        return None
    try:
        from datetime import datetime, timezone

        try:
            date = parsedate_to_datetime(value)
        except (ValueError, TypeError):
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        stamp = date.timestamp()
        return stamp if 0 < stamp <= time.time() + 300 else None
    except (ValueError, TypeError, OverflowError):
        return None


def child_text(item, *names):
    for element in item:
        if element.tag.rsplit("}", 1)[-1] in names and element.text:
            return element.text.strip()
    return ""


def parse_feed(body: bytes, base_url: str) -> list[DocumentInput]:
    if b"\x00" in body or b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
        raise FetchError("unsafe_xml")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise FetchError("invalid_feed") from exc
    if root.tag.rsplit("}", 1)[-1] not in ("rss", "feed", "RDF"):
        raise FetchError("invalid_feed")
    items = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] not in ("item", "entry"):
            continue
        title = plain(child_text(element, "title"))
        link = child_text(element, "link")
        for child in element:
            if child.tag.endswith("link") and child.attrib.get("rel", "alternate") == "alternate":
                link = child.attrib.get("href", link)
        if not title or not link:
            continue
        url = urljoin(base_url, link)
        if urlsplit(url).scheme not in ("http", "https"):
            continue
        items.append(
            DocumentInput(
                url=url,
                title=title[:2000],
                excerpt=plain(child_text(element, "description", "summary", "encoded", "content"))[
                    :1500
                ],
                external_id=child_text(element, "guid", "id") or url,
                signal_value=child_text(element, "approx_traffic") or None,
                published_at=parse_date(
                    child_text(element, "pubDate", "published", "updated", "date")
                ),
            )
        )
    return items[:500]


def cluster_document(session, document: Document):
    if session.get(Mention, document.id):
        return
    words = tokens(document.title)
    match = None
    best = 0.0
    if words:
        query = " OR ".join('"' + word.replace('"', "") + '"' for word in sorted(words)[:15])
        candidates = session.execute(
            text("""SELECT d.id FROM document_fts f
            JOIN documents d ON d.id=f.rowid WHERE document_fts MATCH :query
            AND d.id != :id AND d.observed_at >= :since ORDER BY rank LIMIT 30"""),
            {"query": query, "id": document.id, "since": document.observed_at - 72 * 3600},
        ).scalars()
        for candidate_id in candidates:
            candidate = session.get(Document, candidate_id)
            candidate_mention = session.get(Mention, candidate_id)
            if not candidate_mention:
                continue
            other_words = tokens(candidate.title)
            overlap = len(words & other_words) / max(1, len(words | other_words))
            similarity = (
                0.75 * overlap
                + 0.25
                * SequenceMatcher(None, document.title.lower(), candidate.title.lower()).ratio()
            )
            event = session.get(Event, candidate_mention.event_id)
            if event.status != "merged" and similarity > best and similarity >= 0.66:
                best, match = similarity, event
    if match is None:
        match = Event(
            label=document.title,
            topic=document.topic,
            first_observed_at=document.observed_at,
            confidence=0.6,
        )
        session.add(match)
        session.flush()
    else:
        match.confidence = min(match.confidence if match.confidence > 0.6 else best, best)
    session.add(Mention(document_id=document.id, event_id=match.id, similarity=best or 1))


def store_document(session, source: Source, item: DocumentInput, now=None) -> Document:
    now = now or time.time()
    url = canonical_url(item.url)
    publisher = urlsplit(url).hostname or source.name
    if source.kind == "x" and item.publisher and item.publisher.isdigit():
        publisher = "x:" + item.publisher
    if source.kind == "google_news" and publisher == "news.google.com":
        # An unresolved aggregator URL is evidence, never an independent publisher.
        publisher = "unresolved-google-news"
    external_id = item.external_id or url
    observation = session.scalar(
        select(Observation).where(
            Observation.source_id == source.id, Observation.external_id == external_id
        )
    )
    document = (
        session.get(Document, observation.document_id)
        if observation
        else session.scalar(
            select(Document).where(Document.canonical_url == url, Document.publisher == publisher)
        )
    )
    content_hash = hashlib.sha256((item.title + "\n" + item.excerpt).encode()).hexdigest()
    _, config = active_config(session)
    topic = next(
        (
            topic
            for topic, keywords in config.topic_keywords.items()
            if any(
                tokens(keyword) <= tokens(item.title + " " + item.excerpt)
                for keyword in keywords
                if tokens(keyword)
            )
        ),
        "general",
    )
    if document is None:
        document = Document(
            publisher=publisher,
            group_name=source.group_name if source.kind != "google_news" else publisher,
            canonical_url=url,
            title=item.title,
            excerpt=item.excerpt,
            content_hash=content_hash,
            published_at=item.published_at,
            observed_at=now,
            channel=source.channel,
            topic=topic,
        )
        session.add(document)
        session.flush()
    elif document.content_hash != content_hash:
        session.add(
            DocumentVersion(
                document_id=document.id,
                title=document.title,
                excerpt=document.excerpt,
                content_hash=document.content_hash,
                observed_at=now,
            )
        )
        document.title, document.excerpt, document.content_hash = (
            item.title,
            item.excerpt,
            content_hash,
        )
    if not observation:
        session.add(
            Observation(
                source_id=source.id,
                document_id=document.id,
                external_id=external_id,
                observed_at=now,
            )
        )
    session.flush()
    cluster_document(session, document)
    return document


def source_items(source: Source):
    if source.kind == "x":
        raise FetchError("no_credentials")
    if source.kind == "manual":
        return [], None
    headers = {}
    if source.etag:
        headers["If-None-Match"] = source.etag
    if source.modified:
        headers["If-Modified-Since"] = source.modified
    if source.kind == "web":
        check_robots(source.url)
    response = fetch(source.url, headers)
    if response.status == 304:
        return [], response
    if source.kind != "web":
        return parse_feed(response.body, response.url), response
    soup = BeautifulSoup(response.body, "html.parser")
    feed = soup.find("link", attrs={"type": re.compile(r"application/(rss|atom)\+xml")})
    if feed and feed.get("href"):
        feed_response = fetch(urljoin(response.url, str(feed["href"])))
        # Validators belong to the configured page, not its discovered feed.
        return parse_feed(feed_response.body, feed_response.url), None
    selector = source.options.get("article_selector", "article a[href]")
    result = []
    for node in soup.select(selector)[:100]:
        anchor = node if node.name == "a" else node.find("a", href=True)
        if anchor and anchor.get_text(strip=True):
            link = urljoin(response.url, str(anchor.get("href", "")))
            if urlsplit(link).hostname == urlsplit(response.url).hostname:
                result.append(
                    DocumentInput(url=link, title=anchor.get_text(" ", strip=True)[:2000])
                )
    return result, response


def poll_source(db, source_id: int, vault=None):
    with db.session() as session:
        source = session.get(Source, source_id)
        if not source or not source.enabled:
            return {"skipped": True}
        run = IngestRun(source_id=source_id)
        session.add(run)
        session.flush()
        run_id = run.id
    try:
        if source.kind == "x":
            from .x_connector import poll_x

            with db.session() as session:
                token = vault.get(session, "x") if vault else None
            items, response = poll_x(source, token), None
        else:
            items, response = source_items(source)
        with db.session() as session:
            source = session.get(Source, source_id)
            run = session.get(IngestRun, run_id)
            document_ids = []
            for item in items:
                if source.kind == "google_trends":
                    session.add(
                        TrendSample(
                            source_id=source_id,
                            label=item.title,
                            value=item.signal_value,
                            unit="volume_bucket" if item.signal_value else "search_trend_active",
                            source_url=item.url,
                            geo=source.country,
                            captured_at=run.started_at,
                        )
                    )
                else:
                    document_ids.append(store_document(session, source, item).id)
            source.last_success = time.time()
            source.status, source.error_code = "healthy", None
            source.next_poll = time.time() + source.poll_interval
            if response:
                source.etag = response.headers.get("etag", source.etag)
                source.modified = response.headers.get("last-modified", source.modified)
            run.status, run.count, run.ended_at = "done", len(items), time.time()
        return {"count": len(items), "document_ids": document_ids}
    except Exception as exc:
        code = exc.code if isinstance(exc, FetchError) else "parse_or_storage_error"
        with db.session() as session:
            source = session.get(Source, source_id)
            source.status, source.error_code = "degraded", code
            if code in ("http_401", "http_403", "robots_denied", "not_entitled"):
                source.enabled = False
            source.next_poll = time.time() + (
                3600
                if code in ("http_429", "http_401", "http_403", "no_credentials")
                else source.poll_interval
            )
            run = session.get(IngestRun, run_id)
            run.status, run.error_code, run.ended_at = "failed", code, time.time()
        raise FetchError(code) from exc
