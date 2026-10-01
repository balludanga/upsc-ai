#!/usr/bin/env python3
"""Import a searchable UPSC Prelims question PDF and its official CSV key."""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from app.database import Base, SessionLocal, engine
from app.prelims_bank import import_question_set

logger = logging.getLogger("import_prelims")
UPSC_DOMAIN = "upsc.gov.in"
UPSC_PYQ_PAGE = "https://www.upsc.gov.in/examinations/previous-question-papers"


def _is_upsc_url(value: str) -> bool:
    hostname = (urlparse(value).hostname or "").lower()
    return hostname == UPSC_DOMAIN or hostname.endswith("." + UPSC_DOMAIN)


def _read_pdf(value: str) -> tuple[bytes, str, str | None]:
    parsed = urlparse(value)
    if parsed.scheme in ("http", "https"):
        if not _is_upsc_url(value):
            raise ValueError("Remote question PDFs must be hosted by upsc.gov.in.")
        current_url = value
        for _ in range(5):
            response = requests.get(
                current_url,
                timeout=60,
                allow_redirects=False,
            )
            if response.is_redirect or response.is_permanent_redirect:
                destination = urljoin(current_url, response.headers["Location"])
                if not _is_upsc_url(destination):
                    raise ValueError(
                        "The UPSC PDF URL redirected outside upsc.gov.in."
                    )
                current_url = destination
                continue
            break
        else:
            raise ValueError("The UPSC PDF URL redirected too many times.")
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
            raise ValueError("The supplied UPSC URL did not return a PDF.")
        return response.content, current_url.rsplit("/", 1)[-1], current_url

    path = Path(value).expanduser().resolve()
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise ValueError(f"{path.name} is not a PDF file.")
    return data, path.name, None


def _read_answer_key(path_value: str) -> dict[int, dict[str, str]]:
    path = Path(path_value).expanduser()
    result: dict[int, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as key_file:
        reader = csv.DictReader(key_file)
        required = {"question_number", "correct_option"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(
                "Answer-key CSV must include question_number, correct_option "
                "and optionally explanation columns."
            )
        for row in reader:
            try:
                question_number = int(row["question_number"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Every answer-key row needs a numeric question_number."
                ) from exc
            option = (row.get("correct_option") or "").strip().upper()
            if option not in {"A", "B", "C", "D"}:
                raise ValueError(
                    f"Answer for question {question_number} must be A, B, C, or D."
                )
            if question_number in result:
                raise ValueError(
                    f"Question {question_number} appears more than once "
                    "in the answer-key CSV."
                )
            result[question_number] = {
                "correct_option": option,
                "explanation": (row.get("explanation") or "").strip(),
            }
    if not result:
        raise ValueError("The answer-key CSV contains no answer rows.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import existing UPSC GS Prelims questions into the searchable "
            "question bank. This command never generates question content."
        )
    )
    parser.add_argument(
        "--question-pdf",
        required=True,
        help="Path to a searchable PDF or a direct PDF URL on upsc.gov.in.",
    )
    parser.add_argument(
        "--answer-key",
        required=True,
        help="CSV with question_number,correct_option[,explanation] columns.",
    )
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--paper", default="GS Paper I")
    parser.add_argument(
        "--source-url",
        default=None,
        help=f"Official paper page URL (defaults to {UPSC_PYQ_PAGE}).",
    )
    args = parser.parse_args()

    if args.year < 1950 or args.year > 2100:
        parser.error("--year must be between 1950 and 2100.")
    if args.source_url:
        if not _is_upsc_url(args.source_url):
            parser.error("--source-url must point to upsc.gov.in.")

    pdf_bytes, filename, direct_source_url = _read_pdf(args.question_pdf)
    answer_key = _read_answer_key(args.answer_key)
    source_url = direct_source_url or args.source_url or UPSC_PYQ_PAGE

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        result = import_question_set(
            db,
            pdf_bytes=pdf_bytes,
            answer_key=answer_key,
            year=args.year,
            paper=args.paper,
            source=filename,
            source_url=source_url,
        )

    logger.info(
        "Imported %d question(s); skipped %d duplicate(s); "
        "%d extracted, %d matched to the official key.",
        result["imported"],
        result["skipped_duplicates"],
        result["extracted"],
        result["keyed"],
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
