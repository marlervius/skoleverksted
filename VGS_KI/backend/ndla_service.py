"""NDLA source fetching.

Searches NDLA's open article API (CC-licensed Norwegian learning resources for
upper secondary school) for an article matching the lesson topic, and returns
its plain-text content for use as grounding source material.

The API is open and read-only; no authentication is required.
"""

import html
import logging
import re

import requests

logger = logging.getLogger(__name__)

NDLA_API_BASE = "https://api.ndla.no/article-api/v2/articles"
REQUEST_TIMEOUT = 8  # seconds — generation must not stall on a slow NDLA response
MAX_SOURCE_CHARS = 4500  # keep prompt size bounded, matches teacher-paste limit


def _strip_ndla_html(content: str) -> str:
    """Convert NDLA article HTML to readable plain text.

    Keeps inner text of inline embeds (e.g. concept links), drops image/media
    embeds, turns headings and paragraphs into line breaks.
    """
    text = content
    # Drop embed tags but keep any inner text (inline concept embeds wrap words)
    text = re.sub(r"</?ndlaembed[^>]*>", "", text)
    # Headings and paragraphs become paragraph breaks
    text = re.sub(r"</(h[1-6]|p|li|tr|section|div)>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<(h[1-6])[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*", "\n\n", text)
    return text.strip()


def _is_relevant(topic: str, title: str, meta_description: str) -> bool:
    """Cheap relevance guard: at least one substantial topic word must appear
    in the article title or meta description. Prevents grounding the text in
    an unrelated article when NDLA has no good match."""
    haystack = f"{title} {meta_description}".lower()
    tokens = [t for t in re.findall(r"\w+", topic.lower()) if len(t) >= 4]
    if not tokens:
        tokens = re.findall(r"\w+", topic.lower())
    return any(t in haystack for t in tokens)


def fetch_ndla_source(topic: str, language: str = "nb") -> dict | None:
    """Search NDLA for an article about ``topic`` and return its content.

    Returns a dict with ``text``, ``title``, ``url`` and ``license``, or None
    if no sufficiently relevant article was found or the API was unreachable.
    Never raises — NDLA grounding is best-effort and generation proceeds
    without it on failure.
    """
    try:
        search_resp = requests.get(
            f"{NDLA_API_BASE}/",
            params={"query": topic, "language": language, "page-size": 5},
            timeout=REQUEST_TIMEOUT,
        )
        search_resp.raise_for_status()
        results = search_resp.json().get("results", [])

        match = None
        for result in results:
            title = (result.get("title") or {}).get("title", "")
            meta = (result.get("introduction") or {}).get("introduction", "")
            if _is_relevant(topic, title, meta):
                match = result
                break
        if not match:
            logger.info("NDLA: no relevant article found for topic %r", topic)
            return None

        article_id = match["id"]
        article_resp = requests.get(
            f"{NDLA_API_BASE}/{article_id}",
            params={"language": language},
            timeout=REQUEST_TIMEOUT,
        )
        article_resp.raise_for_status()
        article = article_resp.json()

        raw_content = (article.get("content") or {}).get("content", "")
        text = _strip_ndla_html(raw_content)
        if len(text) < 300:
            logger.info("NDLA: article %s too short to be useful (%d chars)", article_id, len(text))
            return None
        if len(text) > MAX_SOURCE_CHARS:
            # Cut at a paragraph boundary near the limit
            cut = text.rfind("\n\n", 0, MAX_SOURCE_CHARS)
            text = text[: cut if cut > MAX_SOURCE_CHARS // 2 else MAX_SOURCE_CHARS]

        title = (article.get("title") or {}).get("title", "") or f"Artikkel {article_id}"
        license_code = ((article.get("copyright") or {}).get("license") or {}).get("license", "")
        intro = (article.get("introduction") or {}).get("introduction", "")
        full_text = f"{intro}\n\n{text}".strip() if intro else text

        logger.info("NDLA: grounding in article %s (%r, %d chars, license %s)",
                    article_id, title, len(full_text), license_code)
        return {
            "text": full_text,
            "title": title,
            "url": f"https://ndla.no/article/{article_id}",
            "license": license_code,
        }
    except Exception as e:
        logger.warning("NDLA fetch failed for topic %r: %s", topic, e)
        return None
