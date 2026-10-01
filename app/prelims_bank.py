from __future__ import annotations

import hashlib
import io
import json
import logging
import re
from typing import Any, Dict, List, Sequence

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.models import PrelimsQuestion, PrelimsQuestionLevel
from app.rag import chat, clean_json_response

logger = logging.getLogger(__name__)

SUBJECTS = (
    "History",
    "Art and Culture",
    "Geography",
    "Indian Polity",
    "Economy",
    "Environment and Ecology",
    "Science and Technology",
    "Agriculture",
    "International Relations",
    "Current Affairs",
    "Miscellaneous",
)

QUESTION_START = re.compile(r"^\s*(\d{1,3})[.)]\s*(.*)$")
OPTION_START = re.compile(
    r"^\s*(?:\(([A-Da-d])\)|([A-Da-d])[.)])\s*(.*)$"
)


def parse_question_pdf(data: bytes) -> List[Dict[str, Any]]:
    """
    Extract numbered four-option questions without rewriting their wording.
    """
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ValueError(f"Could not read question paper PDF: {exc}") from exc

    lines = "\n".join(pages).replace("\u00a0", " ").splitlines()
    parsed: List[Dict[str, Any]] = []
    current: Dict[str, Any] | None = None
    expected_number = 1

    def finish_current() -> None:
        nonlocal current
        if current is None:
            return

        question = " ".join(current["question"].split()).strip()
        options = [
            " ".join(option.split()).strip()
            for option in current["options"]
        ]
        if question and len(options) == 4 and all(options):
            parsed.append({
                "question_number": current["question_number"],
                "question": question,
                "options": options,
            })
        current = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        question_match = QUESTION_START.match(line)
        if question_match:
            number = int(question_match.group(1))
            if current is None and number == 1:
                current = {
                    "question_number": number,
                    "question": question_match.group(2),
                    "options": [],
                    "option_text": None,
                }
                expected_number += 1
                continue
            if current and len(current["options"]) == 4 and number == expected_number:
                finish_current()
                current = {
                    "question_number": number,
                    "question": question_match.group(2),
                    "options": [],
                    "option_text": None,
                }
                expected_number += 1
                continue

        if current is None or len(current["options"]) == 4:
            continue

        option_match = OPTION_START.match(line)
        if option_match:
            option_label = (option_match.group(1) or option_match.group(2)).upper()
            expected_label = chr(ord("A") + len(current["options"]))
            if option_label == expected_label:
                current["options"].append(option_match.group(3))
                current["option_text"] = len(current["options"]) - 1
                continue

        if current["option_text"] is None:
            current["question"] += " " + line
        else:
            current["options"][current["option_text"]] += " " + line

    finish_current()
    if not parsed:
        raise ValueError(
            "No four-option questions were extracted. "
            "Use a searchable UPSC GS Paper I PDF with numbered questions and A-D options."
        )
    return parsed


def classify_questions(
    questions: Sequence[Dict[str, Any]],
    batch_size: int = 10,
) -> Dict[int, Dict[str, str]]:
    """
    Assign subject/topic labels to extracted questions without generating or
    paraphrasing question content.
    """
    classifications: Dict[int, Dict[str, str]] = {}
    subject_list = ", ".join(SUBJECTS)

    for start in range(0, len(questions), batch_size):
        batch = questions[start:start + batch_size]
        exact_questions = [
            {
                "question_number": item["question_number"],
                "question": item["question"],
            }
            for item in batch
        ]
        prompt = f"""
Classify each supplied UPSC question. Do not answer, rewrite, or create
questions. Use one subject from this exact list: {subject_list}.
Give each item a short topic label supported by its wording.
Assign difficulty as 1 (easier), 2 (standard), or 3 (harder). Return only JSON
in this shape:
{{"questions":[{{"question_number":1,"subject":"Indian Polity","topic":"Constitution","difficulty":2}}]}}

QUESTIONS:
{json.dumps(exact_questions, ensure_ascii=False)}
""".strip()
        raw = chat(
            system_prompt=(
                "You classify existing exam questions. Never create or alter "
                "question content. Return valid JSON only."
            ),
            user_prompt=prompt,
        )
        try:
            payload = json.loads(clean_json_response(raw))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Could not classify imported questions in batch "
                f"{start // batch_size + 1}."
            ) from exc

        batch_numbers = {item["question_number"] for item in batch}
        entries = payload.get("questions") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            raise ValueError(
                f"Question classification batch {start // batch_size + 1} "
                "did not return a questions list."
            )

        for item in entries:
            if not isinstance(item, dict):
                continue
            try:
                number = int(item["question_number"])
            except (KeyError, TypeError, ValueError):
                continue
            subject = str(item.get("subject", "")).strip()
            topic = " ".join(str(item.get("topic", "")).split()).strip()
            try:
                difficulty = int(item.get("difficulty"))
            except (TypeError, ValueError):
                difficulty = 0
            if (
                number in batch_numbers
                and subject in SUBJECTS
                and topic
                and difficulty in (1, 2, 3)
            ):
                classifications[number] = {
                    "subject": subject,
                    "topic": topic[:120],
                    "difficulty": difficulty,
                }

        missing = batch_numbers - classifications.keys()
        if missing:
            raise ValueError(
                "Could not classify question(s) "
                + ", ".join(str(number) for number in sorted(missing))
                + ". No imported questions were saved."
            )

    return classifications


def import_question_set(
    db: Session,
    *,
    pdf_bytes: bytes,
    answer_key: Dict[int, Dict[str, str]],
    year: int,
    paper: str,
    source: str,
    source_url: str | None = None,
) -> Dict[str, int]:
    questions = parse_question_pdf(pdf_bytes)
    keyed_questions = [
        item for item in questions
        if item["question_number"] in answer_key
    ]
    if not keyed_questions:
        raise ValueError(
            "No extracted questions match the supplied answer key. "
            "Provide a key with question_number and correct_option columns."
        )

    classifications = classify_questions(keyed_questions)
    source_id = hashlib.sha256(pdf_bytes).hexdigest()
    inserted = 0
    skipped = 0

    try:
        for item in keyed_questions:
            number = item["question_number"]
            key = answer_key[number]
            correct_option = str(key.get("correct_option", "")).strip().upper()
            if correct_option not in {"A", "B", "C", "D"}:
                raise ValueError(
                    f"Invalid answer key for question {number}; "
                    "correct_option must be A, B, C, or D."
                )

            exists = (
                db.query(PrelimsQuestion.id)
                .filter(
                    PrelimsQuestion.source_id == source_id,
                    PrelimsQuestion.question_number == number,
                )
                .first()
            )
            if exists:
                skipped += 1
                continue

            tags = classifications[number]
            question_record = PrelimsQuestion(
                source_id=source_id,
                question_number=number,
                year=year,
                paper=paper,
                subject=tags["subject"],
                topic=tags["topic"],
                question=item["question"],
                options=item["options"],
                correct_option=correct_option,
                explanation=key.get("explanation") or None,
                source=source,
                source_url=source_url,
            )
            db.add(question_record)
            db.flush()
            db.add(PrelimsQuestionLevel(
                question_id=question_record.id,
                difficulty=tags["difficulty"],
            ))
            inserted += 1

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "extracted": len(questions),
        "keyed": len(keyed_questions),
        "imported": inserted,
        "skipped_duplicates": skipped,
    }


def assemble_question_ids(
    topic: str | None,
    subject: str | None,
    questions: Sequence[PrelimsQuestion],
    count: int,
) -> List[int]:
    """
    Ask the model to select and order IDs from existing questions only.
    Fall back to a shuffled selection if the model is unavailable or returns
    IDs outside the supplied bank.
    """
    if len(questions) <= count:
        return [item.id for item in questions]

    candidates = list(questions[:80])
    prompt = f"""
Select and order up to {count} existing question IDs for a UPSC Prelims quiz.
The requested subject is {subject or "any subject"} and topic is
{topic or "all topics"}.
You may return only IDs from the supplied candidates. Do not create, rewrite,
or return question text. Choose a useful mix and return JSON only:
{{"question_ids":[12,7]}}

CANDIDATE QUESTIONS:
{json.dumps([
    {
        "id": item.id,
        "subject": item.subject,
        "topic": item.topic,
        "year": item.year,
        "question": item.question,
    }
    for item in candidates
], ensure_ascii=False)}
""".strip()
    allowed = {item.id for item in candidates}
    selected: List[int] = []

    try:
        raw = chat(
            system_prompt=(
                "You assemble quizzes only by selecting IDs from an existing "
                "question bank. Never invent or rewrite questions. Return JSON only."
            ),
            user_prompt=prompt,
        )
        payload = json.loads(clean_json_response(raw))
        proposed = payload.get("question_ids", []) if isinstance(payload, dict) else []
        for value in proposed:
            try:
                question_id = int(value)
            except (TypeError, ValueError):
                continue
            if question_id in allowed and question_id not in selected:
                selected.append(question_id)
            if len(selected) == count:
                break
    except Exception:
        logger.warning(
            "AI quiz assembly unavailable; selecting from the matching "
            "question bank in shuffled order.",
            exc_info=True,
        )

    if len(selected) < count:
        import random

        remaining = [item.id for item in candidates if item.id not in selected]
        random.SystemRandom().shuffle(remaining)
        selected.extend(remaining[:count - len(selected)])

    return selected[:count]
