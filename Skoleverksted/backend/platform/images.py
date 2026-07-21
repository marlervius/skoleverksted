"""Shared pedagogical image pipeline for the FOV and VGS applications.

The pipeline is deliberately opt-in.  It resolves at most one image per PDF
and never lets an image failure abort the document generation.

Modes:
    ``none``     no image
    ``commons``  a freely licensed Wikimedia Commons image
    ``ai``       an explicitly labelled Google Gemini illustration
"""

from __future__ import annotations

import base64
from importlib.metadata import PackageNotFoundError, version
import json
import logging
import os
import re
import tempfile
import time
from dataclasses import asdict, dataclass
from html import unescape
from typing import Any, Literal, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

ImageMode = Literal["none", "commons", "ai"]

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "Skoleverksted/1.0 (educational app; https://github.com/marlervius/skoleverksted)"
TEXT_EXCERPT_CHARS = 3000
MAX_GENERATED_IMAGE_BYTES = 15 * 1024 * 1024

# Commons normally rejects NC/ND material already.  We still fail closed when
# metadata is missing or a future API result contains a restrictive licence.
_FREE_LICENSE_MARKERS = (
    "cc0",
    "public domain",
    "pd-",
    "cc by",
    "cc-by",
    "cc by-sa",
    "cc-by-sa",
    "gfdl",
)
_RESTRICTIVE_LICENSE_MARKERS = ("noncommercial", "no derivatives", "cc by-nc", "cc by-nd")


@dataclass
class ImageResult:
    source: Literal["wikimedia", "ai"]
    credit: str
    caption: str = ""
    alt_text: str = ""
    rationale: str = ""
    image_url: Optional[str] = None
    local_path: Optional[str] = None
    source_page_url: Optional[str] = None
    title: Optional[str] = None
    creator: Optional[str] = None
    license: Optional[str] = None

    def public_metadata(self) -> dict:
        """Return serialisable metadata without exposing a server-local path."""
        data = asdict(self)
        data.pop("local_path", None)
        return data


def normalize_image_mode(value: object) -> ImageMode:
    """Normalise old and new client values to the three supported modes."""
    mode = str(value or "none").strip().lower()
    aliases = {
        "real": "commons",
        "wikimedia": "commons",
        "free": "commons",
        "off": "none",
        "false": "none",
    }
    mode = aliases.get(mode, mode)
    return mode if mode in {"none", "commons", "ai"} else "none"  # type: ignore[return-value]


def _api_key() -> str:
    return os.getenv("GOOGLE_IMAGE_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")


def _text_model() -> str:
    return os.getenv("GOOGLE_MODEL", "gemini-3.5-flash")


def _image_model() -> str:
    # Current Google-recommended general image model (configurable without code changes).
    return os.getenv("GOOGLE_IMAGE_MODEL", "gemini-3.1-flash-image")


def _crew_llm() -> Any:
    from crewai import LLM

    key = _api_key()
    if not key:
        raise RuntimeError("Google API key is not configured")
    os.environ.setdefault("GEMINI_API_KEY", key)
    model = _text_model()
    if not model.startswith("gemini/"):
        model = f"gemini/{model.lower()}"
    return LLM(model=model, api_key=key, temperature=0.2)


def _extract_json(value: object) -> Optional[dict]:
    text = str(value or "")
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip("` \r\n")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _fallback_plan(topic: str, subject: str, level: str) -> dict:
    motif = f"{topic}, clearly shown in the context of {subject}"
    return {
        "motif": motif,
        "rationale": f"Bildet gjør hovedtemaet {topic} konkret og lettere å samtale om.",
        "search_queries": [
            f"{topic} {subject} educational photo",
            f"{topic} educational illustration",
            topic,
        ],
        "fallback_search_queries": [topic, f"{topic} {subject}"],
        "generation_prompt": (
            f"A clear educational illustration of {topic} for a {subject} lesson at level {level}. "
            "Show the core concept concretely with one obvious focal point."
        ),
        "caption": topic[:80],
        "alt_text": f"Pedagogisk illustrasjon av {topic}",
    }


def _plan_image(topic: str, subject: str, level: str, text: str, mode: ImageMode) -> dict:
    """Use a dedicated visual-pedagogy agent to create the image brief."""
    fallback = _fallback_plan(topic, subject, level)
    try:
        from crewai import Agent, Crew, Process, Task

        director = Agent(
            role="Bilderegissør for skolemateriale",
            goal="Planlegg ett bilde som gjør læringsstoffet tydeligere, aldri ren dekorasjon.",
            backstory=(
                "Du er ekspert på visuell pedagogikk, kildekritikk og universell utforming. "
                "Du velger konkrete motiv med ett tydelig fokus og tilpasser kompleksiteten til nivået."
            ),
            llm=_crew_llm(),
            verbose=False,
            allow_delegation=False,
        )
        mode_rules = (
            "Planlegg et autentisk foto eller en faglig korrekt illustrasjon som kan finnes på Wikimedia Commons."
            if mode == "commons"
            else (
                "Planlegg en tydelig pedagogisk illustrasjon. Den skal ikke etterligne et dokumentarfoto, "
                "ikke fremstille identifiserbare virkelige personer og ikke inneholde tekst, logoer eller vannmerker."
            )
        )
        task = Task(
            description=f"""Planlegg ETT bilde for læringsarket.

Tema: {topic}
Fag: {subject}
Nivå: {level}
Bildemodus: {mode}
{mode_rules}

Utdrag fra ferdig læringstekst:
---
{text[:TEXT_EXCERPT_CHARS]}
---

Bildet må vise hovedideen konkret, være faglig trygt, fungere på papir og gi
eleven noe relevant å observere eller snakke om. Unngå pynt, kollasjer og tett
tekst. For historiske eller vitenskapelige tema må usikre detaljer utelates.

Svar KUN med ett JSON-objekt:
{{
  "motif": "<hva bildet konkret viser>",
  "rationale": "<hvordan bildet støtter læringen>",
  "search_queries": ["<engelsk Commons-søk 1>", "<søk 2>", "<søk 3>"],
  "fallback_search_queries": ["<kort, bredt engelsk søk 1>", "<bredt søk 2>"],
  "generation_prompt": "<detaljert engelsk bildeprompt>",
  "caption": "<kort bildetekst på samme språk som læringsarket, maks 12 ord>",
  "alt_text": "<kort, konkret alternativ tekst>"
}}""",
            expected_output="Gyldig JSON med motiv, begrunnelse, søk, prompt, bildetekst og alt-tekst.",
            agent=director,
        )
        result = Crew(agents=[director], tasks=[task], process=Process.sequential, verbose=False).kickoff()
        plan = _extract_json(getattr(result, "raw", None) or result)
        if plan and plan.get("motif"):
            return {**fallback, **plan}
    except Exception as exc:
        logger.warning("Bildecrewets planlegging feilet; bruker trygg reserveplan: %s", exc)
    return fallback


def _strip_html(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value or "")).split()).strip()


def _is_free_license(license_name: str) -> bool:
    value = (license_name or "").strip().lower()
    if not value or any(marker in value for marker in _RESTRICTIVE_LICENSE_MARKERS):
        return False
    return any(marker in value for marker in _FREE_LICENSE_MARKERS)


def _query_terms(plan: dict) -> set[str]:
    source = " ".join(
        [str(plan.get("motif", ""))]
        + [
            str(q)
            for field in ("search_queries", "fallback_search_queries")
            for q in plan.get(field, [])
            if isinstance(q, str)
        ]
    ).lower()
    stop = {"with", "from", "that", "this", "photo", "image", "illustration", "educational", "the", "and"}
    return {word for word in re.findall(r"[a-zæøå0-9]{4,}", source) if word not in stop}


def _search_wikimedia(query: str, plan: dict, limit: int = 6) -> list[dict]:
    safe_query = re.sub(r"[<>{}|\\^\[\]`]", " ", query).strip()[:160]
    if not safe_query:
        return []
    try:
        import requests

        response = requests.get(
            WIKIMEDIA_API,
            params={
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrnamespace": 6,
                "gsrsearch": safe_query,
                "gsrlimit": 24,
                "prop": "imageinfo",
                "iiprop": "url|extmetadata|size|mime",
                "iiurlwidth": 1000,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
    except Exception as exc:
        logger.warning("Wikimedia-søk feilet for %r: %s", safe_query, exc)
        return []

    terms = _query_terms(plan)
    candidates: list[dict] = []
    for page in pages.values():
        info_list = page.get("imageinfo") or []
        if not info_list:
            continue
        info = info_list[0]
        if info.get("mime") not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        width, height = int(info.get("width", 0)), int(info.get("height", 0))
        if width < 500 or height < 300:
            continue
        meta = info.get("extmetadata") or {}
        license_name = _strip_html(meta.get("LicenseShortName", {}).get("value", ""))
        if not _is_free_license(license_name):
            continue
        title = str(page.get("title", "")).replace("File:", "", 1)
        description = _strip_html(meta.get("ImageDescription", {}).get("value", ""))[:400]
        creator = _strip_html(meta.get("Artist", {}).get("value", ""))[:160]
        combined = f"{title} {description}".lower()
        if any(bad in combined for bad in ("logo", "coat of arms", "screenshot", "advertisement", "watermark")):
            continue
        matches = sum(1 for term in terms if term in combined)
        if terms and matches == 0:
            continue
        page_url = "https://commons.wikimedia.org/wiki/File:" + quote(title.replace(" ", "_"))
        candidates.append(
            {
                "url": info.get("thumburl") or info.get("url"),
                "original_url": info.get("url"),
                "title": title,
                "description": description,
                "creator": creator,
                "license": license_name,
                "page_url": page_url,
                "score": matches * 1000 + min(width * height / 10000, 500),
            }
        )
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:limit]


def _select_candidate(plan: dict, candidates: list[dict]) -> Optional[dict]:
    """Use a strict critic agent as a semantic quality gate."""
    if not candidates:
        return None
    listing = "\n".join(
        f"[{index}] {item['title']} | {item['description'] or '(ingen beskrivelse)'}"
        for index, item in enumerate(candidates)
    )
    try:
        from crewai import Agent, Crew, Process, Task

        critic = Agent(
            role="Bildekritiker og faktasjekker",
            goal="Velg bare et bilde som tydelig og korrekt viser det planlagte motivet.",
            backstory=(
                "Du er en streng kvalitetsport for skole-PDF-er. Et tvetydig, misvisende eller "
                "løst relatert bilde er verre enn ingen bilde. Du avviser når metadata ikke gir trygg dekning."
            ),
            llm=_crew_llm(),
            verbose=False,
            allow_delegation=False,
        )
        task = Task(
            description=f"""Planlagt motiv: {plan.get('motif')}
Pedagogisk hensikt: {plan.get('rationale')}

Wikimedia-kandidater:
{listing}

Velg én kandidat bare hvis tittel og beskrivelse tydelig dekker motivet og er
egnet for skolebruk. Ellers velg -1.
Svar KUN som JSON: {{"choice": <indeks eller -1>, "reason": "<kort grunn>"}}""",
            expected_output='JSON med "choice" og "reason".',
            agent=critic,
        )
        result = Crew(agents=[critic], tasks=[task], process=Process.sequential, verbose=False).kickoff()
        verdict = _extract_json(getattr(result, "raw", None) or result) or {}
        choice = verdict.get("choice")
        if isinstance(choice, int) and 0 <= choice < len(candidates):
            return candidates[choice]
        logger.info("Bildekritikeren avviste alle Commons-kandidater: %s", verdict.get("reason", ""))
        return None
    except Exception as exc:
        # A high-resolution search hit can still be semantically wrong (for
        # example a building belonging to an organisation whose name contains
        # the topic).  Accuracy is more important than always showing an image.
        logger.warning("Bildekritikeren feilet; avviser kandidatene og fortsetter uten bilde: %s", exc)
        return None


def _verify_image_bytes(plan: dict, image_bytes: bytes, mime_type: str, source: str) -> bool:
    """Use Gemini vision as the final pixel-level quality gate."""
    if not image_bytes or len(image_bytes) > MAX_GENERATED_IMAGE_BYTES or not _api_key():
        return False
    try:
        from google import genai
        from google.genai import types

        model = _text_model().removeprefix("gemini/")
        prompt = f"""Kontroller dette bildet før det settes inn i et skoleark.

Planlagt motiv: {plan.get('motif')}
Pedagogisk hensikt: {plan.get('rationale')}
Undervisningstema: {plan.get('context_topic', '')}
Fag og nivå: {plan.get('context_subject', '')} {plan.get('context_level', '')}
Kildekategori: {source}

Godkjenn hvis hovedmotivet er identifiserbart, faglig relevant og forståelig på
papir. Vurder pedagogisk brukbarhet fremfor estetisk perfeksjon. For autentiske
Wikimedia-bilder av historiske gjenstander, kunstverk, ruiner, manuskripter eller
naturmateriale er alder, patina, sprekker, manglende fragmenter, ujevn bakgrunn
og dokumentasjon av skader IKKE i seg selv avslagsgrunn. Slike spor kan være
faglig verdifulle. Avvis dem bare hvis skadene faktisk skjuler hovedmotivet eller
gjør bildet uleselig i forventet utskriftsstørrelse.

Avvis fortsatt bilder som er feil tema, misvisende, uforståelige, dominert av
irrelevant tekst, logo eller vannmerke, eller har så mye visuelt rot at eleven
ikke finner hovedmotivet. For KI-bilder: avvis også dokumentarisk stil som kan
forveksles med historisk bevis, eller åpenbare anatomiske/fysiske feil.

Svar KUN som JSON:
{{"approved": true eller false, "reason": "<kort begrunnelse>"}}"""
        # Keep a strong reference to the client until the request completes.
        # Chaining ``genai.Client(...).models.generate_content(...)`` can let
        # google-genai close the temporary client before the models call sends
        # its request, which makes every otherwise valid image fail this gate.
        client = genai.Client(api_key=_api_key())
        try:
            response = client.models.generate_content(
                model=model,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ],
            )
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()
        verdict = _extract_json(getattr(response, "text", None) or response) or {}
        approved = verdict.get("approved") is True
        if not approved:
            logger.info("Visuell bildekontroll avviste %s-bildet: %s", source, verdict.get("reason", ""))
        return approved
    except Exception as exc:
        logger.warning("Visuell bildekontroll feilet; bildet avvises: %s", exc)
        return False


def _download_remote_candidate(candidate: dict) -> Optional[tuple[bytes, str]]:
    """Download a Commons image with bounded retries and size checks."""
    try:
        import requests
    except ImportError:
        logger.warning("requests er ikke installert; Commons-bildet kan ikke lastes ned")
        return None

    urls: list[str] = []
    for value in (candidate.get("url"), candidate.get("original_url")):
        url = str(value or "").strip()
        if url and url not in urls:
            urls.append(url)

    last_error: object = "ingen gyldig bilde-URL"
    for url in urls:
        for attempt in range(3):
            response = None
            status = 0
            retry_after = 0.0
            try:
                response = requests.get(
                    url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.8",
                    },
                    timeout=20,
                    stream=True,
                )
                status = int(getattr(response, "status_code", 0) or 0)
                if status == 429:
                    try:
                        retry_after = float(response.headers.get("Retry-After", "0"))
                    except (TypeError, ValueError):
                        retry_after = 0.0
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "image/jpeg").split(";", 1)[0]
                if content_type not in {"image/jpeg", "image/png", "image/webp"}:
                    raise ValueError(f"Ustøttet bildetype: {content_type}")

                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > MAX_GENERATED_IMAGE_BYTES:
                        raise ValueError("Wikimedia-bildet er større enn 15 MB")
                    chunks.append(chunk)
                image_bytes = b"".join(chunks)
                if not image_bytes:
                    raise ValueError("Wikimedia returnerte en tom bildefil")
                return image_bytes, content_type
            except Exception as exc:
                last_error = exc
            finally:
                close = getattr(response, "close", None)
                if callable(close):
                    close()

            retryable = status == 429 or status >= 500 or status == 0
            if not retryable or attempt == 2:
                break
            delay = min(max(retry_after, 0.5 * (2**attempt)), 4.0)
            logger.info(
                "Wikimedia svarte %s; prøver kandidaten igjen om %.1f s",
                status or "med nettverksfeil",
                delay,
            )
            time.sleep(delay)

    logger.warning("Kunne ikke laste Commons-kandidaten %r: %s", candidate.get("title", ""), last_error)
    return None


def _verified_remote_candidate_path(plan: dict, candidate: dict) -> Optional[str]:
    """Download, visually verify and persist the exact bytes used by the PDF."""
    downloaded = _download_remote_candidate(candidate)
    if not downloaded:
        return None
    image_bytes, content_type = downloaded
    if not _verify_image_bytes(plan, image_bytes, content_type, "Wikimedia Commons"):
        return None

    suffix = ".jpg" if content_type in {"image/jpeg", "image/jpg"} else ".png"
    handle = tempfile.NamedTemporaryFile(prefix="skoleverksted_commons_", suffix=suffix, delete=False)
    try:
        handle.write(image_bytes)
        return handle.name
    finally:
        handle.close()


def _collect_commons_candidates(
    plan: dict,
    queries: list[str],
    seen: set[str],
) -> list[dict]:
    candidates: list[dict] = []
    for query in queries[:3]:
        for item in _search_wikimedia(query, plan):
            if item["url"] and item["url"] not in seen:
                seen.add(item["url"])
                candidates.append(item)
    return candidates


def _try_commons_candidates(plan: dict, candidates: list[dict]) -> Optional[ImageResult]:
    chosen = _select_candidate(plan, candidates)
    if not chosen:
        return None

    # The metadata critic's choice is tried first. Search-ranked reserves still
    # pass the stricter pixel-level Gemini gate before they can reach the PDF.
    ordered = [chosen] + [candidate for candidate in candidates if candidate is not chosen]
    for candidate in ordered[:4]:
        local_path = _verified_remote_candidate_path(plan, candidate)
        if not local_path:
            continue
        creator = candidate.get("creator") or "ukjent opphav"
        credit = (
            f'Kilde: Wikimedia Commons · «{candidate["title"]}» · '
            f'{creator} · {candidate["license"]}'
        )
        return ImageResult(
            source="wikimedia",
            image_url=candidate["url"],
            local_path=local_path,
            source_page_url=candidate["page_url"],
            title=candidate["title"],
            creator=candidate.get("creator"),
            license=candidate["license"],
            credit=credit[:500],
            caption=str(plan.get("caption", ""))[:120],
            alt_text=str(plan.get("alt_text") or plan.get("motif", ""))[:240],
            rationale=str(plan.get("rationale", ""))[:500],
        )
    return None


def _commons_image(plan: dict) -> Optional[ImageResult]:
    primary_queries = [
        q.strip() for q in plan.get("search_queries", []) if isinstance(q, str) and q.strip()
    ]
    if not primary_queries:
        primary_queries = [str(plan.get("motif", ""))]

    seen: set[str] = set()
    primary = _collect_commons_candidates(plan, primary_queries, seen)
    result = _try_commons_candidates(plan, primary)
    if result:
        return result

    fallback_queries = [
        q.strip()
        for q in plan.get("fallback_search_queries", [])
        if isinstance(q, str) and q.strip() and q.strip() not in primary_queries
    ]
    if not fallback_queries:
        fallback_queries = [str(plan.get("context_topic") or plan.get("motif", ""))]
    logger.info("Første Commons-runde ga ikke et godkjent bilde; prøver bredere søk")
    fallback = _collect_commons_candidates(plan, fallback_queries, seen)
    return _try_commons_candidates(plan, fallback)


_AI_STYLE_RULES = """
Create a clean educational illustration for a printed school worksheet.
Use one clear focal point, an uncluttered setting, natural colours and strong
visual hierarchy. It must be easy to understand without labels.
Do not include text, letters, numbers, logos, flags, brands or watermarks.
Do not imitate a documentary photograph or imply that an invented scene is
historical evidence. Do not depict a recognisable real person. Avoid stereotypes,
graphic violence, medical diagnoses and unsafe instructions. Aspect ratio 4:3.
"""


def _decode_image_data(value: object) -> Optional[bytes]:
    if isinstance(value, str):
        try:
            return base64.b64decode(value)
        except (ValueError, TypeError):
            return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return None


def _extract_generated_image(response: object) -> tuple[Optional[bytes], str]:
    """Read image output from both Interactions 2.x and generate_content."""
    output_image = getattr(response, "output_image", None)
    image_bytes = _decode_image_data(getattr(output_image, "data", None))
    if image_bytes:
        return image_bytes, str(getattr(output_image, "mime_type", None) or "image/png")

    parts = list(getattr(response, "parts", None) or [])
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        parts.extend(getattr(content, "parts", None) or [])

    for part in parts:
        inline = getattr(part, "inline_data", None)
        image_bytes = _decode_image_data(getattr(inline, "data", None))
        if image_bytes:
            return image_bytes, str(getattr(inline, "mime_type", None) or "image/png")
    return None, "image/png"


def _supports_current_interactions_schema() -> bool:
    """Interactions requires google-genai 2.x after Google's June 2026 sunset."""
    try:
        return int(version("google-genai").split(".", 1)[0]) >= 2
    except (PackageNotFoundError, ValueError):
        return False


def generate_ai_image(prompt: str) -> Optional[str]:
    """Generate one image using Google's current Gemini image API."""
    key = _api_key()
    if not key:
        logger.warning("Google API-nøkkel mangler; KI-bilde hoppes over")
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.warning("google-genai er ikke installert; KI-bilde hoppes over")
        return None

    client = genai.Client(api_key=key)
    full_prompt = f"{prompt.strip()}\n{_AI_STYLE_RULES}".strip()
    image_bytes: Optional[bytes] = None
    mime_type = "image/png"

    # Preferred API. Its failure must not suppress the independent legacy
    # generate_content fallback; that mistake previously made image mode fail
    # completely during Google's Interactions schema migration.
    supports_interactions = _supports_current_interactions_schema()
    interactions = getattr(client, "interactions", None) if supports_interactions else None
    if interactions is not None:
        try:
            interaction = interactions.create(
                model=_image_model(),
                input=full_prompt,
                response_format={
                    "type": "image",
                    "mime_type": "image/png",
                    "aspect_ratio": "4:3",
                    "image_size": "1K",
                },
            )
            image_bytes, mime_type = _extract_generated_image(interaction)
        except Exception as exc:
            logger.warning(
                "Google Interactions-bildekall feilet (%s); prøver generate_content: %s",
                _image_model(),
                exc,
            )
    elif not supports_interactions:
        logger.info("google-genai 1.x oppdaget; bruker generate_content for KI-bildet")

    if not image_bytes:
        try:
            response = client.models.generate_content(
                model=_image_model(),
                contents=[full_prompt],
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
            image_bytes, mime_type = _extract_generated_image(response)
        except Exception as exc:
            logger.warning("Google generate_content-bildekall feilet (%s): %s", _image_model(), exc)

    if not image_bytes or len(image_bytes) > MAX_GENERATED_IMAGE_BYTES:
        logger.warning("Google returnerte ingen gyldig bildedata")
        return None

    suffix = ".jpg" if mime_type in {"image/jpeg", "image/jpg"} else ".png"
    handle = tempfile.NamedTemporaryFile(prefix="skoleverksted_ai_", suffix=suffix, delete=False)
    try:
        handle.write(image_bytes)
        return handle.name
    finally:
        handle.close()


def _ai_image(plan: dict, subject: str) -> Optional[ImageResult]:
    prompt = str(plan.get("generation_prompt") or plan.get("motif") or "").strip()
    if not prompt:
        return None
    local_path = generate_ai_image(prompt)
    if not local_path:
        return None
    try:
        with open(local_path, "rb") as image_file:
            mime_type = "image/jpeg" if local_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
            approved = _verify_image_bytes(plan, image_file.read(), mime_type, "KI")
    except OSError:
        approved = False
    if not approved:
        try:
            os.unlink(local_path)
        except OSError:
            pass
        return None
    english = subject.strip().lower() == "engelsk"
    credit = (
        "AI-generated educational illustration with Google Gemini · not a documentary photograph"
        if english
        else "KI-generert pedagogisk illustrasjon med Google Gemini · ikke et dokumentarfoto"
    )
    return ImageResult(
        source="ai",
        local_path=local_path,
        credit=credit,
        caption=str(plan.get("caption", ""))[:120],
        alt_text=str(plan.get("alt_text") or plan.get("motif", ""))[:240],
        rationale=str(plan.get("rationale", ""))[:500],
    )


def resolve_image(
    mode: object,
    *,
    topic: str,
    subject: str,
    level: str,
    text: str,
) -> Optional[ImageResult]:
    """Resolve one pedagogically meaningful image, or return ``None`` safely."""
    selected = normalize_image_mode(mode)
    if selected == "none":
        return None
    try:
        plan = _plan_image(topic, subject, level, text, selected)
        plan = {
            **plan,
            "context_topic": topic,
            "context_subject": subject,
            "context_level": level,
        }
        return _ai_image(plan, subject) if selected == "ai" else _commons_image(plan)
    except Exception as exc:
        logger.exception("Bildepipeline feilet; PDF fortsetter uten bilde: %s", exc)
        return None
