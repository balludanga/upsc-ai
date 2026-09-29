"""
UPSC page-aware corpus ingestion.

This script supports BOTH local files and selected public web sources.

Host-side defaults:
    Qdrant -> http://localhost:6333
    Ollama -> http://localhost:11434

Local ingestion:
    python3 ingest.py
    python3 ingest.py --reset
    python3 ingest.py --file corpus/Polity/constitution.pdf

Web ingestion:
    python3 ingest.py --web-source pib --limit 20
    python3 ingest.py --web-source niti --limit 10
    python3 ingest.py --web-source upsc --limit 20
    python3 ingest.py --web-source all --limit 10

Direct public URL:
    python3 ingest.py --web-url https://example.gov.in/page

You can combine local and web ingestion in one run.

IMPORTANT:
- Only public URLs are supported.
- Web crawling is restricted to an allowlist of UPSC-relevant domains.
- The crawler stays on the source domain.
- It does not execute JavaScript.
- It stores web URL/title/date metadata internally in Qdrant.
- Learner-facing source metadata is not produced by this script.
- Respect each site's robots.txt, terms, and reuse/licensing conditions.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set
from urllib.parse import urljoin, urlparse, urldefrag

import ollama
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from tqdm import tqdm

from app.config import settings


# =============================================================================
# Logging
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

logger = logging.getLogger(__name__)


# =============================================================================
# Local ingestion configuration
# =============================================================================

CORPUS_DIR = Path("corpus")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
UPSERT_BATCH_SIZE = 64

DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text:latest"

WEB_TIMEOUT_SECONDS = 30
WEB_MAX_BYTES = 25 * 1024 * 1024
WEB_MAX_DEPTH = 1
PIB_MIN_DOCUMENT_CHARS = 180

USER_AGENT = (
    "UPSC-Study-Corpus-Ingestor/1.0 "
    "(educational research; public pages only)"
)


# =============================================================================
# Curated UPSC public-source registry
# =============================================================================
#
# These are public landing/report pages that are useful for UPSC preparation.
# The crawler stays within the same hostname.
#
# Current examples include:
#   PIB: press releases/explainers
#   PRS: legislative and policy research
#   Budget: Economic Survey
#   NITI: government reports
#   RBI: reports/publications
#   MoSPI: official statistics/reports
#   MEA: speeches/statements
#   CAG: audit reports
#   ECI: publications/reports
#   ISRO: space/science material
#   India Code: Acts/sections
#   Legislative Department: legislation/Constitution documents
#   UPSC: official previous question papers
# =============================================================================

WEB_SOURCES: Dict[str, Dict[str, str]] = {
    "pib": {
        # Use the server-rendered All Releases endpoint rather than the
        # JavaScript-heavy homepage. This exposes actual release links.
        "url": "https://www.pib.gov.in/AllRelease.aspx?MenuId=3&lang=1&reg=3",
        "subject": "Current Affairs / Government",
    },
    "prs": {
        "url": "https://prsindia.org/bills/parliament",
        "subject": "Polity / Governance",
    },
    "budget": {
        "url": "https://www.indiabudget.gov.in/economicsurvey/",
        "subject": "Economy",
    },
    "niti": {
        "url": "https://www.niti.gov.in/publications/division-reports",
        "subject": "Economy / Governance / Social Sector",
    },
    "rbi": {
        "url": "https://www.rbi.org.in/scripts/reportsofrbi.aspx",
        "subject": "Economy / Banking / Monetary Policy",
    },
    "mospi": {
        "url": (
            "https://www.mospi.gov.in/"
            "download-reports?combine=&main=&main_cat=All&page=1"
            "&publication_report_cat=All&sub_category=All"
        ),
        "subject": "Economy / Statistics / Society",
    },
    "mea": {
        "url": "https://www.mea.gov.in/Speeches-Statements.htm",
        "subject": "International Relations",
    },
    "cag": {
        "url": "https://cag.gov.in/en/audit-report",
        "subject": "Governance / Economy / Social Sector",
    },
    "eci": {
        "url": "https://www.eci.gov.in/narrative-reports-and-other-publication",
        "subject": "Polity / Elections",
    },
    "isro": {
        "url": "https://www.isro.gov.in/Mission.html",
        "subject": "Science & Technology / Space",
    },
    "indiacode": {
        "url": "https://www.indiacode.nic.in/indiacode/home.jsp",
        "subject": "Polity / Constitution / Law",
    },
    "legislative": {
        "url": "https://www.legislative.gov.in/acts-legislations",
        "subject": "Polity / Constitution / Law",
    },
    "upsc": {
        "url": "https://www.upsc.gov.in/examinations/previous-question-papers",
        "subject": "UPSC / PYQs",
    },
}


# =============================================================================
# Runtime configuration
# =============================================================================

def resolve_qdrant_url(cli_value: Optional[str]) -> str:
    return (
        cli_value
        or os.getenv("INGEST_QDRANT_URL")
        or DEFAULT_QDRANT_URL
    ).rstrip("/")


def resolve_ollama_host(cli_value: Optional[str]) -> str:
    return (
        cli_value
        or os.getenv("INGEST_OLLAMA_HOST")
        or DEFAULT_OLLAMA_HOST
    ).rstrip("/")


def resolve_embedding_model(
    cli_value: Optional[str],
) -> str:
    return (
        cli_value
        or os.getenv("INGEST_EMBEDDING_MODEL")
        or getattr(settings, "embed_model", "")
        or DEFAULT_EMBEDDING_MODEL
    ).strip()


# =============================================================================
# Data structures
# =============================================================================

@dataclass
class WebDocument:
    url: str
    title: str
    subject: str
    content_type: str
    text: str
    published_at: Optional[str] = None


# =============================================================================
# Text utilities
# =============================================================================

def normalize_text(text: str) -> str:
    """
    Normalize extracted text while preserving logical line boundaries.
    """
    text = text.replace("\x00", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines: List[str] = []

    for line in text.split("\n"):
        cleaned = " ".join(line.split())

        if cleaned:
            lines.append(cleaned)

    return "\n".join(lines).strip()


def normalize_url(url: str) -> str:
    """
    Remove URL fragments and trailing noise.
    """
    clean, _fragment = urldefrag(url.strip())

    parsed = urlparse(clean)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError(
            f"Only HTTP/HTTPS URLs are supported: {url}"
        )

    return clean


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def chunk_text(
    text: str,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """
    Generic chunking used by both local text and web HTML.
    """
    text = normalize_text(text)

    if not text:
        return []

    if size <= 0:
        raise ValueError("chunk size must be greater than zero")

    if overlap < 0:
        raise ValueError(
            "chunk overlap cannot be negative"
        )

    if overlap >= size:
        raise ValueError(
            "chunk overlap must be smaller than chunk size"
        )

    chunks: List[str] = []
    step = size - overlap
    start = 0

    while start < len(text):
        end = start + size

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start += step

    return chunks


# =============================================================================
# Local PDF/TXT readers
# =============================================================================

def iter_pdf_chunks(path: Path) -> Iterable[Dict]:
    """
    Yield 1-based page-aware chunks from a local PDF.
    """
    reader = PdfReader(str(path))
    document_id = file_sha256(path)

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        try:
            raw_text = page.extract_text() or ""
        except Exception as exc:
            logger.warning(
                "Could not extract page %s from %s: %s",
                page_number,
                path,
                exc,
            )
            continue

        for chunk_index, chunk in enumerate(
            chunk_text(raw_text),
            start=1,
        ):
            yield {
                "text": chunk,
                "page": page_number,
                "chunk_index": chunk_index,
                "document_id": document_id,
                "url": None,
                "title": path.name,
                "published_at": None,
                "content_type": "pdf",
            }


def iter_txt_chunks(path: Path) -> Iterable[Dict]:
    """
    Yield chunks from a TXT file.
    """
    text = path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    document_id = file_sha256(path)

    for chunk_index, chunk in enumerate(
        chunk_text(text),
        start=1,
    ):
        yield {
            "text": chunk,
            "page": None,
            "chunk_index": chunk_index,
            "document_id": document_id,
            "url": None,
            "title": path.name,
            "published_at": None,
            "content_type": "txt",
        }


# =============================================================================
# Web utilities
# =============================================================================

def hostname_allowed(
    url: str,
    allowed_hosts: Set[str],
) -> bool:
    host = (urlparse(url).hostname or "").lower()

    for allowed in allowed_hosts:
        allowed = allowed.lower().lstrip(".")

        if host == allowed or host.endswith("." + allowed):
            return True

    return False


def same_hostname(
    url: str,
    root_hostname: str,
) -> bool:
    host = (urlparse(url).hostname or "").lower()
    root_hostname = root_hostname.lower()

    return (
        host == root_hostname
        or host.endswith("." + root_hostname)
    )


def looks_like_pdf(
    url: str,
    content_type: str = "",
) -> bool:
    lower_url = url.lower().split("?", 1)[0]
    lower_type = content_type.lower()

    return (
        lower_url.endswith(".pdf")
        or "application/pdf" in lower_type
    )


def is_probably_html(
    content_type: str,
) -> bool:
    return (
        not content_type
        or "text/html" in content_type.lower()
        or "application/xhtml+xml" in content_type.lower()
    )


def extract_published_date(
    soup: BeautifulSoup,
) -> Optional[str]:
    """
    Best-effort extraction of publication/update date.
    """
    candidates = [
        soup.find("meta", attrs={"property": "article:published_time"}),
        soup.find("meta", attrs={"name": "date"}),
        soup.find("meta", attrs={"name": "publishdate"}),
        soup.find("time"),
    ]

    for node in candidates:
        if node is None:
            continue

        value = (
            node.get("content")
            or node.get("datetime")
            or node.get_text(" ", strip=True)
        )

        if value:
            return str(value).strip()

    return None


def extract_html_document(
    url: str,
    html: bytes,
    subject: str,
) -> WebDocument:
    """
    Extract readable text robustly from government HTML pages.

    Some PIB pages contain a ``main``/``article`` wrapper with little or no
    text while the actual release body lives elsewhere in ``body``. We score
    candidate containers and keep the richest visible-text representation.
    """
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    if soup.title:
        title = soup.title.get_text(" ", strip=True)

    published_at = extract_published_date(soup)

    # Work on a copy-like tree in place: remove only clearly non-content
    # elements. Do not remove ``main``/``article`` because they can be the
    # actual content container on one site and empty wrappers on another.
    # PIB is an ASP.NET application and its release body can live inside
    # the page's main <form>. Never remove <form> globally, or the entire
    # release body disappears and extraction collapses to a tiny header/title.
    for tag in soup.find_all(
        ["script", "style", "noscript", "svg", "nav", "footer", "aside"]
    ):
        tag.decompose()

    candidates = []
    selectors = (
        "main",
        "article",
        "[id*=content]",
        "[class*=content]",
        "[id*=Content]",
        "[class*=Content]",
        "body",
    )
    for selector in selectors:
        for node in soup.select(selector)[:20]:
            text = normalize_text(node.get_text("\n", strip=True))
            if text:
                candidates.append((len(text), text))

    if not candidates:
        text = normalize_text(soup.get_text("\n", strip=True))
    else:
        # Richest candidate wins. This specifically handles PIB's sparse
        # wrapper + populated body pattern.
        text = max(candidates, key=lambda item: item[0])[1]

    return WebDocument(
        url=url,
        title=title or url,
        subject=subject,
        content_type="html",
        text=text,
        published_at=published_at,
    )

def extract_pdf_document(
    url: str,
    pdf_bytes: bytes,
    subject: str,
    title: str,
) -> Iterable[Dict]:
    """
    Extract PDF pages while retaining URL + page number.
    """
    reader = PdfReader(
        BytesIO(pdf_bytes)
    )

    document_id = bytes_sha256(
        pdf_bytes
    )

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        try:
            raw_text = page.extract_text() or ""
        except Exception as exc:
            logger.warning(
                "Could not extract web PDF page %s: %s",
                page_number,
                url,
            )
            continue

        for chunk_index, chunk in enumerate(
            chunk_text(raw_text),
            start=1,
        ):
            yield {
                "text": chunk,
                "page": page_number,
                "chunk_index": chunk_index,
                "document_id": document_id,
                "url": url,
                "title": title,
                "published_at": None,
                "content_type": "web_pdf",
                "subject": subject,
            }


def request_url(
    session: requests.Session,
    url: str,
) -> requests.Response:
    """
    Fetch a public URL with bounded timeout/size.
    """
    response = session.get(
        url,
        timeout=WEB_TIMEOUT_SECONDS,
        allow_redirects=True,
    )

    response.raise_for_status()

    final_url = normalize_url(
        response.url
    )

    if not final_url.startswith(
        ("http://", "https://")
    ):
        raise ValueError(
            f"Unsafe redirected URL: {final_url}"
        )

    content_length = response.headers.get(
        "Content-Length"
    )

    if content_length:
        try:
            if int(content_length) > WEB_MAX_BYTES:
                raise ValueError(
                    f"Response exceeds {WEB_MAX_BYTES} bytes: {final_url}"
                )
        except ValueError as exc:
            if "Response exceeds" in str(exc):
                raise
            # Ignore malformed Content-Length.

    if len(response.content) > WEB_MAX_BYTES:
        raise ValueError(
            f"Response exceeds {WEB_MAX_BYTES} bytes: {final_url}"
        )

    return response


def discover_links(
    base_url: str,
    html: bytes,
    allowed_hostname: str,
    limit: int,
    source_key: Optional[str] = None,
) -> List[str]:
    """
    Extract same-domain HTTP/HTTPS content links.

    For PIB, do NOT let ordinary site-navigation links consume the limit.
    PIB's AllRelease page contains release links using the historical
    ``PressReleseDetail.aspx?PRID=...`` spelling, and some responses expose
    the PRID only in embedded HTML/script data. We therefore maintain a
    dedicated PIB candidate pool and fall back to PRID extraction regardless
    of unrelated navigation links.
    """
    soup = BeautifulSoup(html, "html.parser")

    candidates: List[str] = []
    seen: Set[str] = set()

    skip_terms = (
        "login", "signin", "signup", "register", "feedback", "contact",
        "privacy", "terms", "sitemap", "mailto:", "tel:",
    )

    def score_url(absolute: str, anchor_text: str) -> int:
        score = 0
        lower_absolute = absolute.lower()
        if lower_absolute.endswith(".pdf"):
            score += 10
        if source_key == "pib":
            if "pressreleasepage.aspx" in lower_absolute:
                score += 40
            elif "pressreleasedetail.aspx" in lower_absolute:
                score += 38
            elif "pressrelesedetail.aspx" in lower_absolute:
                score += 38
            elif "pressnotedetails.aspx" in lower_absolute:
                score += 25
            elif "factsheetdetails.aspx" in lower_absolute:
                score += 25
            elif "allrelease.aspx" in lower_absolute:
                score += 1
        for term in (
            "report", "publication", "press", "release", "statement",
            "bill", "act", "survey", "paper", "download", "document",
            "mission",
        ):
            if term in lower_absolute:
                score += 2
        if any(term in anchor_text for term in (
            "read", "download", "report", "publication", "pdf",
            "statement", "bill", "act", "press release",
        )):
            score += 2
        return score

    def add_candidate(raw_url: str, anchor_text: str = "") -> None:
        raw_url = raw_url.strip()
        if not raw_url or raw_url.lower().startswith("javascript:"):
            return
        if any(term in raw_url.lower() for term in skip_terms):
            return

        try:
            absolute = normalize_url(urljoin(base_url, raw_url))
        except ValueError:
            return

        if not same_hostname(absolute, allowed_hostname):
            return
        if absolute in seen:
            return

        seen.add(absolute)
        candidates.append(
            f"{score_url(absolute, anchor_text.lower()):02d}|{absolute}"
        )

    def is_pib_content_url(url: str) -> bool:
        path = urlparse(url).path.lower()
        return path.endswith((
            "/pressreleasedetail.aspx",
            "/pressrelesedetail.aspx",
            "/pressreleasepage.aspx",
            "/pressnotedetails.aspx",
            "/factsheetdetails.aspx",
        ))

    # ------------------------------------------------------------------
    # Anchor/data-attribute discovery.
    # ------------------------------------------------------------------
    for anchor in soup.find_all("a"):
        anchor_text = anchor.get_text(" ", strip=True).lower()
        targets: List[str] = []

        for attr in (
            "href", "data-href", "data-url", "data-link", "data-target",
        ):
            value = anchor.get(attr)
            if value:
                targets.append(str(value).strip())

        onclick = anchor.get("onclick")
        if onclick:
            targets.append(str(onclick).strip())

        for target in targets:
            embedded_urls = re.findall(
                r"https?://[^\"'\s)]+|"
                r"/(?:[A-Za-z0-9_./-]+)\.aspx\?[^\"'\s)]+",
                target,
                flags=re.IGNORECASE,
            )

            if embedded_urls:
                for embedded in embedded_urls:
                    try:
                        absolute = normalize_url(
                            urljoin(base_url, embedded)
                        )
                    except ValueError:
                        continue

                    # For PIB, keep only actual content endpoints in the
                    # release-discovery pool.
                    if source_key == "pib" and not is_pib_content_url(absolute):
                        continue
                    add_candidate(embedded, anchor_text)
                continue

            # Normal direct href.
            try:
                absolute = normalize_url(urljoin(base_url, target))
            except ValueError:
                continue

            if source_key == "pib":
                if is_pib_content_url(absolute):
                    add_candidate(target, anchor_text)
            else:
                add_candidate(target, anchor_text)

    # ------------------------------------------------------------------
    # PIB PRID fallback.
    # Always run it when PIB has fewer than ``limit`` actual content links;
    # unrelated navigation links must never suppress this path.
    # ------------------------------------------------------------------
    if source_key == "pib" and len(candidates) < limit:
        raw = html.decode("utf-8", errors="ignore")
        prids: List[str] = []

        patterns = [
            # href/onClick/script references to a PIB release endpoint.
            r"(?:PressReleasePage|PressReleaseDetail|PressReleseDetail)"
            r"\.aspx[^\"'<>()\s]*[?&](?:PRID|prid)=(\d+)",
            # Encoded/query-separated PRID values in HTML/script blobs.
            r"(?:PRID|prid)\s*[=:]\s*[\"']?(\d{5,})",
            # JSON-ish values such as {"PRID":"2314815"}.
            r"[\"'](?:PRID|prid)[\"']\s*:\s*[\"']?(\d{5,})",
        ]

        for pattern in patterns:
            for match in re.findall(pattern, raw, flags=re.IGNORECASE):
                if match not in prids:
                    prids.append(match)

        needed = max(limit - len(candidates), 0)

        # Add a small cushion because a few IDs can occasionally resolve to
        # duplicate/redirected pages.
        for prid in prids[: max(limit * 3, limit)]:
            add_candidate(
                f"/PressReleseDetail.aspx?PRID={prid}",
                "press release",
            )

        logger.info(
            "PIB discovery: actual content links=%d, embedded PRIDs=%d",
            len(candidates),
            len(prids),
        )

    candidates.sort(
        key=lambda item: (int(item.split("|", 1)[0]), item),
        reverse=True,
    )

    result = [
        item.split("|", 1)[1]
        for item in candidates[:limit]
    ]

    if source_key == "pib":
        logger.info("PIB content candidates returned: %d", len(result))

    return result

def canonicalize_web_url(
    url: str,
    source_key: Optional[str] = None,
) -> str:
    """
    Convert known legacy endpoints to a stable rendered form.

    PIB's iframe page is intentionally used first because it exposes the
    release body in a compact server-rendered representation.
    """
    url = normalize_url(url)

    if source_key != "pib":
        return url

    parsed = urlparse(url)
    path_lower = parsed.path.lower()

    if not path_lower.endswith((
        "/pressreleasedetail.aspx",
        "/pressrelesedetail.aspx",
        "/pressrelesedetailm.aspx",
        "/pressreleasepage.aspx",
        "/pressreleaseiframepage.aspx",
    )):
        return url

    from urllib.parse import parse_qs, urlencode
    query = parse_qs(parsed.query)
    prid = (
        query.get("PRID", [""])[0]
        or query.get("prid", [""])[0]
    )
    if not prid:
        return url

    return urljoin(
        url,
        "/PressReleaseIframePage.aspx?" + urlencode({
            "PRID": prid,
            "lang": "1",
            "reg": "3",
        }),
    )


def _extract_prid(url_or_text: str) -> Optional[str]:
    match = re.search(r"(?:PRID|prid)\s*=\s*(\d{5,})", url_or_text)
    if match:
        return match.group(1)
    match = re.search(r"[\"'](?:PRID|prid)[\"']\s*:\s*[\"']?(\d{5,})", url_or_text)
    return match.group(1) if match else None


def _pib_release_urls(prid: str) -> List[str]:
    """Return PIB endpoints from most content-focused to least."""
    return [
        f"https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID={prid}&lang=1&reg=3",
        f"https://www.pib.gov.in/PressReleasePage.aspx?PRID={prid}&lang=1&reg=3",
        f"https://www.pib.gov.in/PressReleaseDetail.aspx?PRID={prid}&lang=1&reg=3",
    ]


def fetch_pib_release(
    session: requests.Session,
    url: str,
    subject: str,
) -> Optional[WebDocument]:
    """Fetch one PIB release with endpoint fallbacks and extraction diagnostics."""
    prid = _extract_prid(url)
    candidates = _pib_release_urls(prid) if prid else [url]

    tried: Set[str] = set()
    for candidate in candidates:
        if candidate in tried:
            continue
        tried.add(candidate)
        try:
            response = request_url(session, candidate)
            content_type = response.headers.get("Content-Type", "")
            if not is_probably_html(content_type):
                logger.warning(
                    "PIB release unsupported content: %s type=%s",
                    response.url,
                    content_type,
                )
                continue

            document = extract_html_document(
                normalize_url(response.url),
                response.content,
                subject,
            )
            logger.info(
                "PIB release fetch: prid=%s status=%s final=%s bytes=%d text_chars=%d",
                prid or "?",
                response.status_code,
                response.url,
                len(response.content),
                len(document.text),
            )

            if len(document.text) >= PIB_MIN_DOCUMENT_CHARS:
                return document

            logger.warning(
                "PIB release extraction too short: prid=%s text_chars=%d title=%r",
                prid or "?",
                len(document.text),
                document.title[:120],
            )
        except Exception as exc:
            logger.warning("PIB endpoint failed %s: %s", candidate, exc)

    return None

def web_seed_documents(
    session: requests.Session,
    source_key: str,
    limit: int,
) -> List[WebDocument]:
    """
    Fetch a curated source landing page and discover a bounded set of
    same-domain content pages/PDFs.
    """
    source = WEB_SOURCES[source_key]

    seed_url = normalize_url(
        source["url"]
    )

    seed_response = request_url(
        session,
        seed_url,
    )

    logger.info(
        "Web seed fetched: %s status=%s final=%s content_type=%s bytes=%d",
        source_key,
        seed_response.status_code,
        seed_response.url,
        seed_response.headers.get("Content-Type", ""),
        len(seed_response.content),
    )

    # Follow redirects for parsing/discovery. PIB in particular redirects
    # some legacy endpoints to alternate rendered paths.
    effective_seed_url = normalize_url(
        seed_response.url
    )

    if not is_probably_html(
        seed_response.headers.get(
            "Content-Type",
            "",
        )
    ):
        raise RuntimeError(
            f"Web source seed is not HTML: {seed_url}"
        )

    root_hostname = (
        urlparse(effective_seed_url)
        .hostname
        or ""
    ).lower()

    links = discover_links(
        base_url=effective_seed_url,
        html=seed_response.content,
        allowed_hostname=root_hostname,
        limit=limit,
        source_key=source_key,
    )

    logger.info(
        "Web discovery: %s -> %d candidate links (seed=%s)",
        source_key,
        len(links),
        effective_seed_url,
    )

    if not links:
        logger.warning(
            "Web discovery returned 0 links for %s. The site may be "
            "JavaScript-driven, blocking automated requests, or using a "
            "different server-rendered endpoint.",
            source_key,
        )

    documents: List[WebDocument] = []

    # Do not index PIB's listing page itself; it is navigation rather than
    # study content. For other sources, retain a useful landing page.
    if source_key != "pib":
        try:
            seed_document = extract_html_document(
                effective_seed_url,
                seed_response.content,
                source["subject"],
            )
            if len(seed_document.text) >= 500:
                documents.append(seed_document)
        except Exception:
            logger.exception(
                "Could not extract seed page: %s",
                seed_url,
            )

    for url in links:
        try:
            if source_key == "pib":
                document = fetch_pib_release(
                    session,
                    url,
                    source["subject"],
                )
                if document is not None:
                    documents.append(document)
                continue

            url = canonicalize_web_url(
                url,
                source_key,
            )

            response = request_url(
                session,
                url,
            )

            content_type = response.headers.get(
                "Content-Type",
                "",
            )

            if looks_like_pdf(
                url,
                content_type,
            ):
                # Web PDFs are handled later because a single URL can yield
                # several page-aware Qdrant records.
                documents.append(
                    WebDocument(
                        url=url,
                        title=Path(
                            urlparse(url).path
                        ).name or url,
                        subject=source["subject"],
                        content_type="web_pdf",
                        text="",
                    )
                )
                continue

            if not is_probably_html(
                content_type
            ):
                continue

            document = extract_html_document(
                url,
                response.content,
                source["subject"],
            )

            if len(document.text) >= 300:
                documents.append(document)

        except Exception as exc:
            logger.warning(
                "Skipping web URL %s: %s",
                url,
                exc,
            )

    return documents


def fetch_web_url(
    session: requests.Session,
    url: str,
    subject: str,
) -> tuple[Optional[WebDocument], Optional[bytes], str]:
    """
    Fetch one direct public URL.

    Returns:
        HTML document OR None
        PDF bytes OR None
        effective content type
    """
    response = request_url(
        session,
        url,
    )

    final_url = normalize_url(
        response.url
    )

    content_type = response.headers.get(
        "Content-Type",
        "",
    )

    if looks_like_pdf(
        final_url,
        content_type,
    ):
        return None, response.content, "web_pdf"

    if not is_probably_html(
        content_type
    ):
        raise ValueError(
            f"Unsupported web content type: {content_type}"
        )

    return (
        extract_html_document(
            final_url,
            response.content,
            subject,
        ),
        None,
        "html",
    )


# =============================================================================
# Connectivity
# =============================================================================

def check_qdrant(
    client: QdrantClient,
    url: str,
) -> None:
    try:
        client.get_collections()
    except Exception as exc:
        raise RuntimeError(
            "Cannot connect to Qdrant.\n"
            f"URL: {url}\n"
            "Make sure Qdrant is running and port 6333 is published."
        ) from exc

    logger.info("Qdrant connection: OK")


def try_embedding_model(
    client: ollama.Client,
    model_name: str,
) -> bool:
    try:
        response = client.embed(
            model=model_name,
            input="UPSC ingestion connectivity test",
        )

        embeddings = response.get(
            "embeddings"
        )

        return bool(
            isinstance(embeddings, list)
            and embeddings
            and isinstance(
                embeddings[0],
                list,
            )
            and embeddings[0]
        )

    except Exception:
        return False


def check_ollama(
    client: ollama.Client,
    host: str,
    configured_model: str,
) -> str:
    try:
        client.list()
    except Exception as exc:
        raise RuntimeError(
            "Cannot connect to Ollama.\n"
            f"Host: {host}\n"
            "Make sure native Ollama is running."
        ) from exc

    candidates: List[str] = []

    def add(value: str) -> None:
        value = value.strip()
        if value and value not in candidates:
            candidates.append(value)

    add(configured_model)

    base = configured_model.split(
        ":",
        1,
    )[0]

    if base:
        add(f"{base}:latest")

    add(DEFAULT_EMBEDDING_MODEL)

    for candidate in candidates:
        logger.info(
            "Testing embedding model: %s",
            candidate,
        )

        if try_embedding_model(
            client,
            candidate,
        ):
            logger.info(
                "Embedding model ready: %s",
                candidate,
            )
            return candidate

    raise RuntimeError(
        "Ollama is reachable, but the configured embedding model could not "
        "generate an embedding.\n"
        f"Tried: {', '.join(candidates)}\n"
        "Verify with 'ollama list' and install the embedding model if needed."
    )


# =============================================================================
# Embeddings
# =============================================================================

def get_embedding(
    client: ollama.Client,
    text: str,
    model_name: str,
) -> List[float]:
    if not text or not text.strip():
        raise ValueError(
            "Cannot embed empty text."
        )

    try:
        response = client.embed(
            model=model_name,
            input=text,
        )

        embeddings = response.get(
            "embeddings"
        )

        if (
            isinstance(embeddings, list)
            and embeddings
            and isinstance(
                embeddings[0],
                list,
            )
        ):
            return embeddings[0]

    except (AttributeError, TypeError):
        pass

    response = client.embeddings(
        model=model_name,
        prompt=text,
    )

    embedding = response.get(
        "embedding"
    )

    if not embedding:
        raise RuntimeError(
            "Ollama did not return an embedding."
        )

    return embedding


# =============================================================================
# Qdrant
# =============================================================================

def collection_exists(
    client: QdrantClient,
) -> bool:
    collections = (
        client.get_collections()
        .collections
    )

    return any(
        item.name
        == settings.qdrant_collection
        for item in collections
    )


def ensure_collection(
    client: QdrantClient,
    vector_size: int,
) -> None:
    if collection_exists(client):
        return

    logger.info(
        "Creating Qdrant collection '%s'...",
        settings.qdrant_collection,
    )

    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE,
        ),
    )


def reset_collection(
    client: QdrantClient,
) -> None:
    if not collection_exists(client):
        logger.info(
            "Collection '%s' does not exist; nothing to reset.",
            settings.qdrant_collection,
        )
        return

    logger.info(
        "Deleting collection '%s'...",
        settings.qdrant_collection,
    )

    client.delete_collection(
        collection_name=settings.qdrant_collection
    )


# =============================================================================
# Local file discovery
# =============================================================================

def get_files(
    single_file: Optional[str],
) -> List[Path]:
    if single_file:
        path = Path(
            single_file
        ).expanduser()

        if not path.exists():
            raise FileNotFoundError(
                f"File not found: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Not a file: {path}"
            )

        if path.suffix.lower() not in {
            ".pdf",
            ".txt",
        }:
            raise ValueError(
                "Only .pdf and .txt files are supported."
            )

        return [path]

    if not CORPUS_DIR.exists():
        raise FileNotFoundError(
            f"Corpus directory not found: {CORPUS_DIR}"
        )

    return sorted(
        path
        for path in CORPUS_DIR.rglob("*")
        if (
            path.is_file()
            and path.suffix.lower()
            in {".pdf", ".txt"}
        )
    )


# =============================================================================
# Point creation
# =============================================================================

def make_point(
    record: Dict,
    vector: List[float],
    source_path: Optional[Path] = None,
) -> PointStruct:
    """
    Build a Qdrant point with unified local/web metadata.
    """
    text = record["text"]

    page = record.get("page")
    document_id = record.get(
        "document_id",
        "unknown",
    )
    chunk_index = record.get(
        "chunk_index",
        1,
    )
    url = record.get("url")
    title = record.get(
        "title",
        "",
    )
    published_at = record.get(
        "published_at"
    )
    content_type = record.get(
        "content_type",
        "unknown",
    )
    subject = record.get(
        "subject"
    )

    if not subject:
        subject = (
            source_path.parent.name
            if source_path
            and source_path.parent.name
            else "unknown"
        )

    stable_namespace = (
        url
        or str(
            source_path
            or document_id
        )
    )

    stable_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        (
            f"{stable_namespace}:"
            f"{document_id}:"
            f"{page}:"
            f"{chunk_index}"
        ),
    )

    page_value = (
        str(page)
        if page is not None
        else "na"
    )

    payload = {
        "text": text,
        "subject": subject,
        "source": (
            str(source_path)
            if source_path
            else url
            or title
            or "unknown"
        ),
        "document_id": document_id,
        "page": page,
        "chunk_index": chunk_index,
        "source_type": content_type,
        "chunk_id": (
            f"{document_id[:12]}:"
            f"{page_value}:"
            f"{chunk_index}"
        ),
    }

    # Web-only metadata remains internal to the vector corpus.
    if url:
        payload["url"] = url

    if title:
        payload["title"] = title

    if published_at:
        payload["published_at"] = (
            published_at
        )

    payload["ingested_at"] = (
        datetime.now(timezone.utc)
        .isoformat()
    )

    return PointStruct(
        id=str(stable_id),
        vector=vector,
        payload=payload,
    )


# =============================================================================
# Local ingestion
# =============================================================================

def ingest_file(
    path: Path,
    ollama_client: ollama.Client,
    qdrant_client: QdrantClient,
    embedding_model: str,
) -> int:
    records = (
        iter_pdf_chunks(path)
        if path.suffix.lower() == ".pdf"
        else iter_txt_chunks(path)
    )

    points: List[PointStruct] = []

    for record in records:
        record["subject"] = path.parent.name

        vector = get_embedding(
            ollama_client,
            record["text"],
            embedding_model,
        )

        points.append(
            make_point(
                record,
                vector,
                source_path=path,
            )
        )

    if not points:
        logger.warning(
            "No extractable text found in %s",
            path,
        )
        return 0

    ensure_collection(
        qdrant_client,
        len(points[0].vector),
    )

    for start in range(
        0,
        len(points),
        UPSERT_BATCH_SIZE,
    ):
        qdrant_client.upsert(
            collection_name=settings.qdrant_collection,
            points=points[
                start:start + UPSERT_BATCH_SIZE
            ],
        )

    return len(points)


# =============================================================================
# Web ingestion
# =============================================================================

def ingest_web_document(
    document: WebDocument,
    session: requests.Session,
    ollama_client: ollama.Client,
    qdrant_client: QdrantClient,
    embedding_model: str,
) -> int:
    """
    Ingest one HTML page or a web PDF.
    """
    if document.content_type == "web_pdf":
        response = request_url(
            session,
            document.url,
        )

        title = document.title

        points: List[PointStruct] = []

        for record in extract_pdf_document(
            document.url,
            response.content,
            document.subject,
            title,
        ):
            vector = get_embedding(
                ollama_client,
                record["text"],
                embedding_model,
            )

            points.append(
                make_point(
                    record,
                    vector,
                )
            )

        for start in range(
            0,
            len(points),
            UPSERT_BATCH_SIZE,
        ):
            qdrant_client.upsert(
                collection_name=settings.qdrant_collection,
                points=points[
                    start:start + UPSERT_BATCH_SIZE
                ],
            )

        return len(points)

    records = chunk_text(
        document.text
    )

    if not records:
        return 0

    document_id = bytes_sha256(
        document.text.encode(
            "utf-8",
            errors="ignore",
        )
    )

    points: List[PointStruct] = []

    for chunk_index, chunk in enumerate(
        records,
        start=1,
    ):
        record = {
            "text": chunk,
            "page": None,
            "chunk_index": chunk_index,
            "document_id": document_id,
            "url": document.url,
            "title": document.title,
            "published_at": document.published_at,
            "content_type": "webpage",
            "subject": document.subject,
        }

        vector = get_embedding(
            ollama_client,
            chunk,
            embedding_model,
        )

        points.append(
            make_point(
                record,
                vector,
            )
        )

    ensure_collection(
        qdrant_client,
        len(points[0].vector),
    )

    for start in range(
        0,
        len(points),
        UPSERT_BATCH_SIZE,
    ):
        qdrant_client.upsert(
            collection_name=settings.qdrant_collection,
            points=points[
                start:start + UPSERT_BATCH_SIZE
            ],
        )

    return len(points)


def validate_direct_web_url(
    url: str,
) -> str:
    """
    Only allow direct URL ingestion from the curated public-source domains.
    """
    url = normalize_url(url)

    allowed_hosts = {
        (urlparse(source["url"]).hostname or "")
        for source in WEB_SOURCES.values()
    }

    allowed_hosts = {
        host.lower()
        for host in allowed_hosts
        if host
    }

    if not hostname_allowed(
        url,
        allowed_hosts,
    ):
        allowed = ", ".join(
            sorted(allowed_hosts)
        )

        raise ValueError(
            "Direct web ingestion is restricted to curated UPSC public "
            "domains.\n"
            f"URL host: {urlparse(url).hostname}\n"
            f"Allowed domains: {allowed}"
        )

    return url


def ingest_web_source(
    source_key: str,
    limit: int,
    session: requests.Session,
    ollama_client: ollama.Client,
    qdrant_client: QdrantClient,
    embedding_model: str,
) -> int:
    """
    Ingest a bounded set of pages/PDFs from one curated source.
    """
    if source_key not in WEB_SOURCES:
        raise ValueError(
            f"Unknown web source: {source_key}"
        )

    source = WEB_SOURCES[source_key]

    logger.info(
        "Web source: %s (%s)",
        source_key,
        source["url"],
    )

    documents = web_seed_documents(
        session=session,
        source_key=source_key,
        limit=limit,
    )

    logger.info(
        "Web documents discovered for %s: %d",
        source_key,
        len(documents),
    )

    if not documents:
        logger.warning(
            "No web documents discovered for %s; 0 chunks will be indexed.",
            source_key,
        )

    total_chunks = 0

    for document in tqdm(
        documents,
        desc=f"Web: {source_key}",
    ):
        try:
            count = ingest_web_document(
                document=document,
                session=session,
                ollama_client=ollama_client,
                qdrant_client=qdrant_client,
                embedding_model=embedding_model,
            )

            total_chunks += count

            logger.info(
                "%s -> %d chunks",
                document.url,
                count,
            )

        except Exception as exc:
            logger.warning(
                "Failed web document %s: %s",
                document.url,
                exc,
            )

    return total_chunks


def ingest_direct_web_url(
    url: str,
    session: requests.Session,
    subject: str,
    ollama_client: ollama.Client,
    qdrant_client: QdrantClient,
    embedding_model: str,
) -> int:
    url = validate_direct_web_url(
        url
    )

    document, pdf_bytes, content_type = (
        fetch_web_url(
            session,
            url,
            subject,
        )
    )

    if pdf_bytes is not None:
        document = WebDocument(
            url=url,
            title=Path(
                urlparse(url).path
            ).name or url,
            subject=subject,
            content_type="web_pdf",
            text="",
        )

    if document is None:
        raise RuntimeError(
            "Could not build web document."
        )

    return ingest_web_document(
        document=document,
        session=session,
        ollama_client=ollama_client,
        qdrant_client=qdrant_client,
        embedding_model=embedding_model,
    )


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest local UPSC files and curated public web sources "
            "into a page-aware Qdrant corpus."
        )
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the existing Qdrant collection first.",
    )

    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Ingest one local PDF/TXT file.",
    )

    parser.add_argument(
        "--web-source",
        choices=sorted(
            list(WEB_SOURCES.keys())
            + ["all"]
        ),
        default=None,
        help=(
            "Ingest from a curated public UPSC source. "
            "Use 'all' for all registered sources."
        ),
    )

    parser.add_argument(
        "--web-url",
        type=str,
        default=None,
        help=(
            "Ingest one direct public URL from an allowlisted UPSC domain."
        ),
    )

    parser.add_argument(
        "--web-subject",
        type=str,
        default="Web / UPSC",
        help="Subject tag for --web-url.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help=(
            "Maximum same-domain links discovered per web source. "
            "Default: 10."
        ),
    )

    parser.add_argument(
        "--qdrant-url",
        type=str,
        default=None,
        help=(
            "Qdrant URL. Defaults to INGEST_QDRANT_URL "
            "or http://localhost:6333."
        ),
    )

    parser.add_argument(
        "--ollama-host",
        type=str,
        default=None,
        help=(
            "Ollama URL. Defaults to INGEST_OLLAMA_HOST "
            "or http://localhost:11434."
        ),
    )

    parser.add_argument(
        "--embedding-model",
        type=str,
        default=None,
        help=(
            "Embedding model override."
        ),
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=CHUNK_SIZE,
        help=f"Chunk size. Default: {CHUNK_SIZE}.",
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=CHUNK_OVERLAP,
        help=f"Chunk overlap. Default: {CHUNK_OVERLAP}.",
    )

    return parser.parse_args()


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    args = parse_args()

    if args.limit < 1:
        raise ValueError(
            "--limit must be at least 1."
        )

    if args.chunk_size <= 0:
        raise ValueError(
            "--chunk-size must be greater than zero."
        )

    if (
        args.chunk_overlap < 0
        or args.chunk_overlap >= args.chunk_size
    ):
        raise ValueError(
            "--chunk-overlap must be >= 0 and smaller than --chunk-size."
        )

    global CHUNK_SIZE, CHUNK_OVERLAP

    CHUNK_SIZE = args.chunk_size
    CHUNK_OVERLAP = args.chunk_overlap

    qdrant_url = resolve_qdrant_url(
        args.qdrant_url
    )

    ollama_host = resolve_ollama_host(
        args.ollama_host
    )

    configured_embedding_model = (
        resolve_embedding_model(
            args.embedding_model
        )
    )

    logger.info(
        "Ingestion configuration:"
    )
    logger.info(
        "  Qdrant: %s",
        qdrant_url,
    )
    logger.info(
        "  Ollama: %s",
        ollama_host,
    )
    logger.info(
        "  Configured embedding model: %s",
        configured_embedding_model,
    )
    logger.info(
        "  Collection: %s",
        settings.qdrant_collection,
    )
    logger.info(
        "  Chunk size: %d",
        CHUNK_SIZE,
    )
    logger.info(
        "  Chunk overlap: %d",
        CHUNK_OVERLAP,
    )

    # -------------------------------------------------------------------------
    # Clients
    # -------------------------------------------------------------------------

    ollama_client = ollama.Client(
        host=ollama_host
    )

    qdrant_client = QdrantClient(
        url=qdrant_url,
        api_key=(
            settings.qdrant_api_key
            or None
        ),
    )

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/pdf;q=0.9,*/*;q=0.8"
            ),
        }
    )

    # -------------------------------------------------------------------------
    # Verify dependencies before reset.
    # -------------------------------------------------------------------------

    check_qdrant(
        qdrant_client,
        qdrant_url,
    )

    embedding_model = check_ollama(
        ollama_client,
        ollama_host,
        configured_embedding_model,
    )

    if args.reset:
        reset_collection(
            qdrant_client
        )

    # We only need the collection if there is something to ingest.
    has_local = bool(
        args.file
        or CORPUS_DIR.exists()
    )

    has_web = bool(
        args.web_source
        or args.web_url
    )

    if not has_local and not has_web:
        print(
            "Nothing selected.\n\n"
            "Examples:\n"
            "  python3 ingest.py --reset\n"
            "  python3 ingest.py --web-source pib --limit 20\n"
            "  python3 ingest.py --web-source upsc --limit 20\n"
            "  python3 ingest.py --web-url https://www.upsc.gov.in/examinations/previous-question-papers"
        )
        return

    # -------------------------------------------------------------------------
    # Local files.
    # -------------------------------------------------------------------------

    total_chunks = 0
    failed_files = 0

    if has_local:
        files = get_files(
            args.file
        )

        if files:
            logger.info(
                "Found %d local file(s).",
                len(files),
            )

            for path in tqdm(
                files,
                desc="Local files",
            ):
                try:
                    count = ingest_file(
                        path,
                        ollama_client,
                        qdrant_client,
                        embedding_model,
                    )

                    total_chunks += count

                    logger.info(
                        "%s -> %d chunks",
                        path,
                        count,
                    )

                except Exception:
                    failed_files += 1

                    logger.exception(
                        "Failed local file: %s",
                        path,
                    )
        else:
            logger.info(
                "No local PDF/TXT files found."
            )

    # -------------------------------------------------------------------------
    # Curated web sources.
    # -------------------------------------------------------------------------

    web_sources = []

    if args.web_source:
        if args.web_source == "all":
            web_sources = sorted(
                WEB_SOURCES.keys()
            )
        else:
            web_sources = [
                args.web_source
            ]

    for source_key in web_sources:
        try:
            total_chunks += ingest_web_source(
                source_key=source_key,
                limit=args.limit,
                session=session,
                ollama_client=ollama_client,
                qdrant_client=qdrant_client,
                embedding_model=embedding_model,
            )

        except Exception:
            failed_files += 1

            logger.exception(
                "Failed web source: %s",
                source_key,
            )

    # -------------------------------------------------------------------------
    # Direct web URL.
    # -------------------------------------------------------------------------

    if args.web_url:
        try:
            total_chunks += ingest_direct_web_url(
                url=args.web_url,
                session=session,
                subject=args.web_subject,
                ollama_client=ollama_client,
                qdrant_client=qdrant_client,
                embedding_model=embedding_model,
            )

        except Exception:
            failed_files += 1

            logger.exception(
                "Failed direct web URL: %s",
                args.web_url,
            )

    # -------------------------------------------------------------------------
    # Summary.
    # -------------------------------------------------------------------------

    print()
    print("=" * 68)
    print("UPSC PAGE-AWARE INGESTION COMPLETE")
    print("=" * 68)
    print(
        f"Collection:         {settings.qdrant_collection}"
    )
    print(
        f"Qdrant:             {qdrant_url}"
    )
    print(
        f"Ollama:             {ollama_host}"
    )
    print(
        f"Embedding model:    {embedding_model}"
    )
    print(
        f"Chunks indexed:     {total_chunks}"
    )
    print(
        f"Failures:            {failed_files}"
    )
    print(
        f"Chunk size:         {CHUNK_SIZE}"
    )
    print(
        f"Chunk overlap:      {CHUNK_OVERLAP}"
    )
    print("=" * 68)

    if failed_files:
        sys.exit(1)


if __name__ == "__main__":
    main()
