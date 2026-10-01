from __future__ import annotations

import io
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from app.config import settings
from app.rag import chat_vision

try:
    import pymupdf
except ImportError:  # pragma: no cover - optional at import time
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - optional at import time
    Image = None


logger = logging.getLogger(__name__)


PDF_MIME_TYPES = {"application/pdf", "application/x-pdf"}

IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/tiff",
    "image/gif",
}

SUPPORTED_MIME_TYPES = PDF_MIME_TYPES | IMAGE_MIME_TYPES

OCR_ENGINES = {"rapidocr", "ollama-vision", "auto"}

# Images longer than this edge are downscaled before transcription.
MAX_IMAGE_EDGE = 2200

# Images are transcribed in small batches so inference stays responsive.
IMAGE_BATCH_SIZE = 4

# A PDF with at least this many extractable characters is treated as
# digital (typed) text and is not sent to the OCR engine.
PDF_TEXT_LAYER_THRESHOLD = 240

# Refuse to build an evaluation input larger than this.
MAX_TRANSCRIBED_CHARS = 12000

MIN_USEFUL_CHARS = 20


class UploadError(ValueError):
    """
    A user-facing upload/transcription failure.
    """


TRANSCRIPTION_PROMPT = """
You are a transcription engine for handwritten UPSC Mains answer scripts.

Transcribe EXACTLY what is written on the supplied pages.

Rules:
- The images are pages of the SAME answer, in order. Read every page and
  continue the text across page boundaries.
- Do NOT summarise, rewrite, correct grammar, add facts or improve the answer.
- Preserve headings, numbering and bullet markers.
- Join words and sentences split across line breaks, but keep paragraph breaks.
- If a word or line cannot be read, write [illegible] in its place.
  Never guess and never invent text.
- Do NOT output markdown fences, commentary, page labels or the question.
- Output only the transcribed text of the answer.
""".strip()


@dataclass
class Transcription:
    text: str
    pages: int
    images: int
    engine: str
    warnings: List[str] = field(default_factory=list)
    filenames: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pages": self.pages,
            "images": self.images,
            "engine": self.engine,
            "warnings": self.warnings,
            "filenames": self.filenames,
        }


def _strip_wrappers(raw: str) -> str:
    text = (raw or "").strip()

    text = re.sub(
        r"^```(?:text|markdown)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text.strip()


def _drop_page_labels(text: str) -> str:
    return re.sub(
        r"(?im)^\s*(?:page\s*)?(?:p(?:age)?\.?\s*)?\d+\s*[:.)-]\s*",
        "",
        text,
    ).strip()


def _has_point_markers(text: str) -> bool:
    """
    Detect numbered or bulleted lines that survived transcription.
    """
    return bool(
        re.search(
            r"(?m)^\s*(?:\d+[.)]|[-•*])\s+",
            text,
        )
    )


def _normalise_image(data: bytes) -> bytes:
    """
    Apply EXIF rotation, convert to RGB and downscale oversized photos.
    """
    if Image is None:
        return data

    try:
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source) or source

            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")

            longest = max(image.size)

            if longest > MAX_IMAGE_EDGE:
                scale = MAX_IMAGE_EDGE / longest
                image = image.resize(
                    (
                        max(1, int(image.width * scale)),
                        max(1, int(image.height * scale)),
                    ),
                    Image.LANCZOS,
                )

            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=88)
            return buffer.getvalue()

    except Exception:
        logger.warning("Image normalisation failed; sending bytes as-is.")
        return data


def _render_pdf(
    data: bytes,
    warnings: List[str],
) -> Tuple[List[bytes], str]:
    """
    Render PDF pages to images for transcription.

    Returns the rendered pages plus any embedded text layer. When the PDF
    is typed rather than handwritten the text layer is returned instead of
    rendering pages, which avoids an expensive vision call.
    """
    if pymupdf is None:  # pragma: no cover - depends on install
        raise UploadError(
            "PDF support is unavailable on the server. "
            "Upload page images instead, or install pymupdf."
        )

    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise UploadError(
            "That PDF could not be read. It may be corrupted or encrypted."
        ) from exc

    try:
        page_count = document.page_count

        if page_count == 0:
            raise UploadError("That PDF has no pages.")

        embedded_text = "\n".join(
            (document.load_page(index).get_text() or "").strip()
            for index in range(page_count)
        )

        letters = len(
            re.sub(r"\s+", "", embedded_text)
        )

        if letters >= PDF_TEXT_LAYER_THRESHOLD:
            warnings.append(
                "A text layer was found in the PDF, so the embedded "
                "text was used instead of reading the pages as images."
            )
            return ([], embedded_text)

        limit = max(1, settings.upload_max_pages)

        if page_count > limit:
            warnings.append(
                f"Only the first {limit} of {page_count} pages were read."
            )

        zoom = max(1.0, min(3.0, settings.upload_render_dpi / 72))
        matrix = pymupdf.Matrix(zoom, zoom)

        pages: List[bytes] = []

        for index in range(min(page_count, limit)):
            pixmap = document.load_page(index).get_pixmap(
                matrix=matrix,
                alpha=False,
            )
            pages.append(_normalise_image(pixmap.tobytes("jpeg")))

        return (pages, "")

    finally:
        document.close()


def _prepare_upload(
    filename: str,
    content_type: str,
    data: bytes,
    warnings: List[str],
) -> Tuple[List[bytes], int, str]:
    """
    Turn one upload into zero or more images plus its embedded text.
    """
    mime = (content_type or "").split(";")[0].strip().lower()

    if mime in PDF_MIME_TYPES or filename.lower().endswith(".pdf"):
        pages, embedded_text = _render_pdf(data, warnings)
        return (pages, len(pages), embedded_text)

    if mime in IMAGE_MIME_TYPES or filename.lower().endswith(
        (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")
    ):
        return ([_normalise_image(data)], 1, "")

    raise UploadError(
        f"'{filename}' is not a supported file. "
        "Upload a PDF or a JPG/PNG image."
    )


def transcribe_uploads(
    uploads: List[Tuple[str, str, bytes]],
) -> Transcription:
    """
    Transcribe uploaded photos / scanned PDFs into plain text.

    `uploads` is a list of (filename, content_type, data) tuples.
    """
    if not uploads:
        raise UploadError("Attach at least one photo or PDF.")

    if len(uploads) > settings.upload_max_files:
        raise UploadError(
            f"Attach at most {settings.upload_max_files} files at a time."
        )

    warnings: List[str] = []
    filenames: List[str] = []
    images: List[bytes] = []
    embedded_parts: List[str] = []
    page_count = 0

    for filename, content_type, data in uploads:
        if not data:
            continue

        filenames.append(filename)

        pages, rendered_pages, embedded_text = _prepare_upload(
            filename=filename,
            content_type=content_type,
            data=data,
            warnings=warnings,
        )

        images.extend(pages)
        page_count += rendered_pages

        if embedded_text:
            embedded_parts.append(embedded_text)

    if not images and not embedded_parts:
        raise UploadError("The uploaded files were empty.")

    parts: List[str] = list(embedded_parts)
    engine = "pdf-text-layer"
    scores: List[float] = []

    if images:
        engine = resolve_engine()

        for start in range(0, len(images), IMAGE_BATCH_SIZE):
            batch = images[start:start + IMAGE_BATCH_SIZE]

            if engine == "rapidocr":
                page_text, page_scores = _transcribe_with_rapidocr(
                    batch
                )
                scores.extend(page_scores)
            else:
                page_text = _transcribe_with_vision_model(
                    batch=batch,
                    total=len(images),
                )

            parts.append(page_text)

    text = "\n\n".join(
        _drop_page_labels(_strip_wrappers(part))
        for part in parts
        if part and part.strip()
    ).strip()

    if len(re.sub(r"\s+", "", text)) < MIN_USEFUL_CHARS:
        raise UploadError(
            "No readable text was found in the upload. "
            "Try a sharper, well-lit photo of straight-on, "
            "unruled paper."
        )

    if scores:
        mean_score = sum(scores) / len(scores)

        if mean_score < settings.ocr_min_confidence:
            warnings.append(
                "The handwriting was read with low confidence, so some "
                "words may be wrong. Proofread the text before evaluating."
            )

    if images and not _has_point_markers(text):
        warnings.append(
            "List markers such as '1.' or '-' are often lost when "
            "reading handwriting. Re-add them before evaluating so the "
            "point-wise structure is judged correctly."
        )

    if len(text) > MAX_TRANSCRIBED_CHARS:
        warnings.append(
            "The transcription was very long and was truncated."
        )
        text = text[:MAX_TRANSCRIBED_CHARS]

    return Transcription(
        text=text,
        pages=page_count,
        images=len(images),
        engine=engine,
        warnings=warnings,
        filenames=filenames,
    )


# -----------------------------------------------------------------------------
# Engine: RapidOCR (PP-OCR, CPU only)
# -----------------------------------------------------------------------------

_rapidocr_engine: Any = None
_rapidocr_lock = threading.Lock()


class _DropRapidOCRInfo(logging.Filter):
    """
    RapidOCR resets its logger to INFO while loading models.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.WARNING


def _quiet_rapidocr_logs() -> None:
    """
    Keep RapidOCR's model-loading chatter out of the app logs.
    """
    rapid_logger = logging.getLogger("RapidOCR")
    rapid_logger.setLevel(logging.WARNING)

    if not any(
        isinstance(existing, _DropRapidOCRInfo)
        for existing in rapid_logger.filters
    ):
        rapid_logger.addFilter(_DropRapidOCRInfo())

    for handler in rapid_logger.handlers:
        handler.setLevel(logging.WARNING)


def _get_rapidocr() -> Any:
    """
    Build the RapidOCR engine once and reuse it.

    Model loading costs a second or two, so it is kept in a module-level
    singleton rather than rebuilt per request.
    """
    global _rapidocr_engine

    if _rapidocr_engine is not None:
        return _rapidocr_engine

    with _rapidocr_lock:
        if _rapidocr_engine is not None:
            return _rapidocr_engine

        _quiet_rapidocr_logs()

        try:
            from rapidocr import RapidOCR
        except ImportError as exc:
            raise UploadError(
                "Handwritten uploads are not enabled on this server. "
                "Install the OCR dependencies (pip install -r "
                "requirements.txt) or type your answer instead."
            ) from exc

        try:
            _rapidocr_engine = RapidOCR()
        except Exception as exc:
            logger.exception("RapidOCR engine could not be started.")
            raise UploadError(
                "The handwriting reader could not be started on this "
                "server. Try again or type your answer instead."
            ) from exc

        _quiet_rapidocr_logs()

        return _rapidocr_engine


def _result_texts(result: Any) -> List[str]:
    """
    Pull detected lines out of a RapidOCR result.
    """
    if result is None:
        return []

    texts = getattr(result, "txts", None)

    if texts is None and isinstance(result, tuple):
        texts = result[1] if len(result) > 1 else None

    if not texts:
        return []

    return [
        str(text).strip()
        for text in texts
        if str(text).strip()
    ]


def _result_scores(result: Any) -> List[float]:
    scores = getattr(result, "scores", None)

    if scores is None and isinstance(result, tuple):
        scores = result[2] if len(result) > 2 else None

    if not scores:
        return []

    return [
        float(score)
        for score in scores
        if score is not None
    ]


def _transcribe_with_rapidocr(
    images: List[bytes],
) -> Tuple[str, List[float]]:
    """
    Transcribe page images locally with PP-OCR.

    Runs on CPU, needs no model download beyond the package itself, and
    keeps every answer image on the machine.
    """
    engine = _get_rapidocr()

    parts: List[str] = []
    scores: List[float] = []

    for data in images:
        try:
            result = engine(data)
        except Exception as exc:
            logger.exception("RapidOCR inference failed.")
            raise UploadError(
                "That page could not be read. Try re-uploading a "
                "clearer photo, or type your answer instead."
            ) from exc

        lines = _result_texts(result)

        if not lines:
            parts.append("")
            continue

        parts.append("\n".join(lines))
        scores.extend(_result_scores(result))

    return ("\n".join(parts), scores)


# -----------------------------------------------------------------------------
# Engine: Ollama vision model (optional)
# -----------------------------------------------------------------------------

def _transcribe_with_vision_model(
    batch: List[bytes],
    total: int,
) -> str:
    scope = (
        f"Transcribe all {total} page images attached to this request."
        if total > 1
        else "Transcribe this single page image."
    )

    try:
        return chat_vision(
            system_prompt=TRANSCRIPTION_PROMPT,
            user_prompt=scope,
            images=batch,
        )
    except Exception as exc:
        logger.exception("Handwritten answer transcription failed.")
        raise UploadError(
            "Handwritten answers could not be read right now. "
            f"Check that the vision model '{settings.vision_model}' is "
            "installed (for example: ollama pull "
            f"{settings.vision_model})."
        ) from exc


def resolve_engine() -> str:
    """
    Decide which OCR engine to use for image uploads.
    """
    engine = (settings.ocr_engine or "rapidocr").strip().lower()

    if engine not in OCR_ENGINES:
        raise UploadError(
            f"Unknown OCR engine '{settings.ocr_engine}'. "
            "Set OCR_ENGINE to rapidocr, ollama-vision or auto."
        )

    if engine != "auto":
        return engine

    try:
        import importlib.util

        if importlib.util.find_spec("rapidocr") is not None:
            return "rapidocr"
    except Exception:  # pragma: no cover - defensive
        pass

    return "ollama-vision"
