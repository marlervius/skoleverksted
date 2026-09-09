"""Shared source identity, safe retrieval and snapshot provenance.

This is intentionally independent of Gemini/compendium code.  A model URL is
only a candidate; it becomes usable evidence after a bounded, safe fetch has
created a snapshot with an excerpt.  The networking helper is small enough to
be faked in ordinary tests.
"""

from __future__ import annotations

import hashlib
import html
import ipaddress
import logging
import re
import socket
import time
from dataclasses import dataclass
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from html.parser import HTMLParser
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .models import SourceSnapshot, TruthSource
from .quality_runtime import QualityLayerCancelled

logger = logging.getLogger(__name__)


_TRACKING_PARAMETERS = frozenset({"gclid", "dclid", "fbclid", "mc_cid", "mc_eid", "_ga"})
_BLOCKED_HOSTS = frozenset({"localhost", "metadata.google.internal", "metadata", "host.docker.internal"})
_ALLOWED_MIME_PREFIXES = ("text/", "application/json", "application/xml", "application/xhtml+xml")
_MAX_REDIRECTS = 4
_MAX_BYTES = 1_000_000


class UnsafeSourceUrl(ValueError):
    """The URL is not an externally fetchable HTTP(S) resource."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _clean_query(query: str) -> str:
    retained = [
        (key, value)
        for key, value in parse_qsl(query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in _TRACKING_PARAMETERS
    ]
    return urlencode(retained, doseq=True)


def canonical_source_url(value: object) -> str:
    """Canonicalise only syntactic/tracking differences, never page identity."""
    raw = str(value or "").strip()
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return ""
    host = parsed.hostname.casefold().rstrip(".")
    try:
        port = parsed.port
    except ValueError:
        return ""
    netloc = host if port is None else f"{host}:{port}"
    path = quote(parsed.path or "/", safe="/:@!$&'()*+,;=-._~%")
    return urlunsplit((scheme, netloc, path, _clean_query(parsed.query), ""))


def source_id_for(url: str) -> str:
    return hashlib.sha256(f"source:{url}".encode("utf-8")).hexdigest()[:24]


def _is_public_ip(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return True
    return not (parsed.is_private or parsed.is_loopback or parsed.is_link_local or parsed.is_multicast or parsed.is_reserved or parsed.is_unspecified)


def safe_source_url(value: object, *, resolve_dns: bool = False) -> str:
    url = canonical_source_url(value)
    if not url:
        raise UnsafeSourceUrl("Ugyldig kilde-URL.")
    host = (urlsplit(url).hostname or "").casefold()
    if host in _BLOCKED_HOSTS or host.endswith((".localhost", ".local", ".internal")) or not _is_public_ip(host):
        raise UnsafeSourceUrl("Kilde-URL peker til en intern eller reservert adresse.")
    if resolve_dns:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)}
        except socket.gaierror as exc:
            raise UnsafeSourceUrl("Kildevert kunne ikke slås opp.") from exc
        if not addresses or any(not _is_public_ip(address) for address in addresses):
            raise UnsafeSourceUrl("Kildevert peker til en intern eller reservert adresse.")
    return url


class _PageText(HTMLParser):
    """Prefer article text; never turn a truncated script into evidence."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.body: list[str] = []
        self.article: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack) - 1 - self.stack[::-1].index(tag)]

    def handle_data(self, data):
        if any(tag in {"script", "style", "noscript", "nav", "header", "footer", "form", "svg", "head"} for tag in self.stack):
            return
        self.body.append(data)
        if "main" in self.stack or "article" in self.stack:
            self.article.append(data)


def _plain_excerpt(raw: bytes, *, limit: int = 4000, charset: str = "utf-8", is_html: bool = True) -> str:
    try:
        text = raw.decode(charset, errors="replace")
    except LookupError:
        text = raw.decode("utf-8", errors="replace")
    if is_html:
        parser = _PageText()
        parser.feed(text)
        parser.close()
        text = " ".join(parser.article or parser.body)
    return " ".join(html.unescape(text).split())[:limit]


@dataclass(frozen=True)
class FetchObservation:
    source: TruthSource
    snapshot: SourceSnapshot


def fetch_source_snapshot(
    value: object,
    *,
    title: str = "",
    publisher: str = "",
    origin: str = "model",
    timeout_seconds: float = 8.0,
    max_bytes: int = _MAX_BYTES,
) -> FetchObservation:
    """Safely fetch a small text snapshot while validating every redirect."""
    observed = safe_source_url(value, resolve_dns=True)
    current = observed
    aliases: list[str] = []
    opener = build_opener(_NoRedirect())
    started = time.monotonic()
    status = "source_unavailable"
    excerpt = ""
    final_url = observed
    for _ in range(_MAX_REDIRECTS + 1):
        remaining = timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            status = "timeout"
            break
        try:
            request = Request(current, headers={"User-Agent": "Skoleverksted evidence fetch/3.0", "Accept": "text/html,text/plain,application/json,application/xml;q=0.8"})
            response = opener.open(request, timeout=max(0.1, remaining))
            final_url = current
            code = getattr(response, "status", response.getcode())
            if 300 <= code < 400:
                location = response.headers.get("Location", "")
                response.close()
                if not location:
                    status = "source_unavailable"
                    break
                aliases.append(current)
                current = safe_source_url(urljoin(current, location), resolve_dns=True)
                final_url = current
                continue
            try:
                final_url = safe_source_url(response.geturl(), resolve_dns=True)
                content_type = str(response.headers.get("Content-Type", ""))
                mime = content_type.split(";", 1)[0].casefold()
                if not any(mime.startswith(prefix) for prefix in _ALLOWED_MIME_PREFIXES):
                    status = "unsupported_mime"
                    break
                # A snapshot is a bounded excerpt, not a complete page copy.
                # Large HTML shells must not discard valid article text.
                raw = response.read(max(1, min(max_bytes, _MAX_BYTES)))
                charset_match = re.search(r"charset=[\"']?([^;\s\"']+)", content_type, re.I)
                excerpt = _plain_excerpt(
                    raw, charset=charset_match.group(1) if charset_match else "utf-8",
                    is_html=mime in {"text/html", "application/xhtml+xml"},
                )
                status = "fetched" if excerpt else "irrelevant"
            finally:
                response.close()
            break
        except HTTPError as exc:
            try:
                if 300 <= exc.code < 400 and exc.headers.get("Location"):
                    aliases.append(current)
                    current = safe_source_url(urljoin(current, exc.headers["Location"]), resolve_dns=True)
                    final_url = current
                    continue
                status = "not_found" if exc.code == 404 else "forbidden" if exc.code in {401, 403} else "source_unavailable"
                final_url = current
                break
            finally:
                exc.close()
        except (TimeoutError, socket.timeout):
            status = "timeout"
            break
        except (URLError, UnsafeSourceUrl, OSError):
            status = "source_unavailable"
            break
    digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest() if excerpt else ""
    snapshot = SourceSnapshot(
        source_id=source_id_for(final_url), content_hash=digest, excerpt=excerpt,
        fetch_status=status,
    )
    source = TruthSource(
        source_id=snapshot.source_id,
        title=(title or final_url)[:300], url=final_url, observed_uri=observed,
        redirect_aliases=aliases, publisher=publisher[:180], origin=origin if origin in {"teacher", "grounding", "model"} else "model",  # type: ignore[arg-type]
        fetch_status=status, snapshot_id=snapshot.snapshot_id, snapshot_hash=digest,
        excerpt=excerpt, fetched_at=snapshot.fetched_at,
    )
    return FetchObservation(source=source, snapshot=snapshot)


def collect_source_snapshots(
    values: Iterable[object], *, cancel_check: Callable[[], bool] | None = None,
    timeout_seconds: float = 24.0, request_id: str = "",
) -> list[TruthSource]:
    """Fetch observed candidates concurrently within one cancellation budget."""
    sources = observed_sources(values)
    pending = [source for source in sources if not source_has_usable_snapshot(source)]
    if not pending:
        return sources
    deadline = time.monotonic() + timeout_seconds

    def fetch(source: TruthSource) -> TruthSource:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or (cancel_check and cancel_check()):
            return source.model_copy(update={"fetch_status": "timeout"})
        try:
            observation = fetch_source_snapshot(
                source.url, title=source.title, publisher=source.publisher,
                origin=source.origin, timeout_seconds=min(8.0, remaining),
            )
            return observation.source.model_copy(update={
                "observed_uri": source.observed_uri or source.url,
                "redirect_aliases": list(dict.fromkeys([
                    *source.redirect_aliases, source.url, *observation.source.redirect_aliases,
                ]))[:12],
            })
        except Exception:
            return source.model_copy(update={"fetch_status": "source_unavailable"})

    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="source-snapshot")
    futures = {executor.submit(fetch, source): source for source in pending}
    try:
        while futures and time.monotonic() < deadline:
            if cancel_check and cancel_check():
                raise QualityLayerCancelled("source retrieval cancelled")
            done, _ = wait(futures, timeout=min(0.1, max(0, deadline - time.monotonic())), return_when=FIRST_COMPLETED)
            for future in done:
                original = futures.pop(future)
                sources[sources.index(original)] = future.result()
        for original in futures.values():
            sources[sources.index(original)] = original.model_copy(update={"fetch_status": "timeout"})
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    logger.info("source_snapshots_collected", extra={
        "request_id": request_id, "source_count": len(sources),
        "fetched_count": sum(source_has_usable_snapshot(source) for source in sources),
        "fetch_statuses": [source.fetch_status for source in sources],
    })
    return sources


def source_has_usable_snapshot(source: TruthSource) -> bool:
    return bool(source.snapshot_id and source.snapshot_hash and source.excerpt.strip() and source.fetch_status == "fetched")


def source_from_observed(value: object) -> TruthSource | None:
    """Read source metadata without treating it as proof.

    Callers can provide a previously fetched snapshot.  Otherwise this returns
    a model/teacher/grounding candidate with no usable snapshot.
    """
    if isinstance(value, str):
        raw: dict[str, Any] = {"url": value, "title": value}
    elif isinstance(value, dict):
        raw = value
    else:
        raw = {name: getattr(value, name, "") for name in (
            "url", "title", "publisher", "origin", "fetch_status", "published_at",
            "observed_uri", "redirect_aliases", "snapshot_id", "snapshot_hash", "excerpt", "fetched_at",
        )}
    url = canonical_source_url(raw.get("url"))
    if not url:
        return None
    origin = str(raw.get("origin") or "model")
    if origin not in {"teacher", "grounding", "model"}:
        origin = "model"
    fetch_status = str(raw.get("fetch_status") or "model_reported")
    allowed_statuses = {"provided", "grounded", "model_reported", "fetched", "source_unavailable", "forbidden", "not_found", "timeout", "unsupported_mime", "irrelevant"}
    if fetch_status not in allowed_statuses:
        fetch_status = "model_reported"
    excerpt = str(raw.get("excerpt") or "")[:4000]
    snapshot_hash = str(raw.get("snapshot_hash") or "")[:128]
    snapshot_id = str(raw.get("snapshot_id") or "")[:80]
    # Metadata claiming ``fetched`` is not enough. A snapshot carries both an
    # excerpt and its content hash.
    if fetch_status == "fetched" and not (excerpt and snapshot_hash and snapshot_id):
        fetch_status = "model_reported"
    return TruthSource(
        source_id=str(raw.get("source_id") or source_id_for(url))[:80],
        title=str(raw.get("title") or url)[:300], url=url,
        observed_uri=str(raw.get("observed_uri") or url)[:1000],
        redirect_aliases=[str(item)[:1000] for item in (raw.get("redirect_aliases") or [])[:12]],
        publisher=str(raw.get("publisher") or "")[:180],
        published_at=str(raw.get("published_at") or "")[:80],
        origin=origin, fetch_status=fetch_status, snapshot_id=snapshot_id,
        snapshot_hash=snapshot_hash, excerpt=excerpt, fetched_at=str(raw.get("fetched_at") or "")[:80],
    )


def observed_sources(values: Iterable[object]) -> list[TruthSource]:
    sources: list[TruthSource] = []
    for value in values:
        source = source_from_observed(value)
        if source is None:
            continue
        existing = next((item for item in sources if item.url == source.url), None)
        if existing is None:
            sources.append(source)
        elif source_has_usable_snapshot(source) and not source_has_usable_snapshot(existing):
            sources[sources.index(existing)] = source
    return sources[:50]
