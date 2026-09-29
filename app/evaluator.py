from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from app.rag import (
    analyze_question_demand,
    build_context,
    chat,
    extract_sources,
    retrieve,
)

logger = logging.getLogger(__name__)


EVALUATION_PROMPT = """
You are a UPSC Mains answer evaluator.

Evaluate the student's answer against the question and the supplied
question-demand analysis.

Use ONLY the supplied corpus context for factual corrections.

Do NOT rewrite the entire answer.
Do NOT invent facts, examples, reports, committees, judgments or thinkers.
Do NOT expose source names, page numbers, filenames, chunk IDs or corpus
metadata.

Return ONLY valid JSON using this exact structure:

{
  "overall_feedback": "",
  "question_demand": {
    "addressed": true,
    "feedback": ""
  },
  "structure": {
    "introduction": true,
    "body": true,
    "point_wise": true,
    "conclusion": true,
    "feedback": ""
  },
  "dimensions": {
    "covered": [],
    "missing": [],
    "feedback": ""
  },
  "analysis": {
    "strengths": [],
    "weaknesses": [],
    "feedback": ""
  },
  "evidence": {
    "strengths": [],
    "unsupported_claims": [],
    "feedback": ""
  },
  "keywords_to_add": [],
  "examples_to_add": [],
  "strengths": [],
  "improvements": [],
  "word_count": 0
}

Be specific and concise.
""".strip()


def _clean_json_response(raw: str) -> str:
    text = (raw or "").strip()

    text = re.sub(
        r"^```(?:json)?\s*",
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

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end > start:
        text = text[start:end + 1]

    return text.strip()


def _point_count(answer: str) -> int:
    return len(
        re.findall(
            r"(?m)^\s*(?:\d+[.)]|[-•*])\s+",
            answer,
        )
    )


def _fallback_evaluation(
    answer: str,
    word_limit: int,
    demand: Any,
) -> Dict[str, Any]:
    """
    Deterministic fallback if the evaluator model returns invalid JSON.
    """
    word_count = len(answer.split())
    points = _point_count(answer)

    normalized = answer.lower()

    has_intro = any(
        term in normalized
        for term in ("introduction", "intro", "background")
    )

    has_conclusion = any(
        term in normalized
        for term in ("conclusion", "in conclusion", "to conclude")
    )

    has_body = points >= 2

    return {
        "overall_feedback": (
            "Automatic evaluation fallback: "
            "the answer was structurally checked, but detailed content "
            "evaluation could not be completed."
        ),
        "question_demand": {
            "addressed": True,
            "feedback": (
                f"Detected directive: {demand.directive}. "
                "Review the detailed demand manually."
            ),
        },
        "structure": {
            "introduction": has_intro,
            "body": has_body,
            "point_wise": points >= 2,
            "conclusion": has_conclusion,
            "feedback": f"{points} numbered/bullet points detected.",
        },
        "dimensions": {
            "covered": [],
            "missing": demand.dimensions,
            "feedback": "Detailed dimension analysis unavailable.",
        },
        "analysis": {
            "strengths": [],
            "weaknesses": [],
            "feedback": "Detailed analysis unavailable.",
        },
        "evidence": {
            "strengths": [],
            "unsupported_claims": [],
            "feedback": "Detailed evidence analysis unavailable.",
        },
        "keywords_to_add": [],
        "examples_to_add": [],
        "strengths": [],
        "improvements": [
            "Check the answer against each dimension demanded by the question.",
            "Ensure the body is point-wise and analytical.",
        ],
        "word_count": word_count,
    }


def _normalise_evaluation(
    data: Dict[str, Any],
    answer: str,
    word_limit: int,
    demand: Any,
) -> Dict[str, Any]:
    """
    Make model output safe and predictable for the frontend.
    """
    fallback = _fallback_evaluation(
        answer=answer,
        word_limit=word_limit,
        demand=demand,
    )

    def bool_or(value: Any, default: bool) -> bool:
        return value if isinstance(value, bool) else default

    def list_or(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ][:12]

    structure = data.get("structure", {})
    if not isinstance(structure, dict):
        structure = {}

    dimensions = data.get("dimensions", {})
    if not isinstance(dimensions, dict):
        dimensions = {}

    analysis = data.get("analysis", {})
    if not isinstance(analysis, dict):
        analysis = {}

    evidence = data.get("evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}

    word_count = len(answer.split())

    return {
        "overall_feedback": str(
            data.get("overall_feedback")
            or fallback["overall_feedback"]
        ).strip(),
        "question_demand": {
            "addressed": bool_or(
                data.get("question_demand", {}).get("addressed")
                if isinstance(data.get("question_demand"), dict)
                else None,
                fallback["question_demand"]["addressed"],
            ),
            "feedback": str(
                (
                    data.get("question_demand", {}).get("feedback")
                    if isinstance(data.get("question_demand"), dict)
                    else ""
                )
                or fallback["question_demand"]["feedback"]
            ).strip(),
        },
        "structure": {
            "introduction": bool_or(
                structure.get("introduction"),
                fallback["structure"]["introduction"],
            ),
            "body": bool_or(
                structure.get("body"),
                fallback["structure"]["body"],
            ),
            "point_wise": bool_or(
                structure.get("point_wise"),
                fallback["structure"]["point_wise"],
            ),
            "conclusion": bool_or(
                structure.get("conclusion"),
                fallback["structure"]["conclusion"],
            ),
            "feedback": str(
                structure.get("feedback")
                or fallback["structure"]["feedback"]
            ).strip(),
        },
        "dimensions": {
            "covered": list_or(dimensions.get("covered")),
            "missing": list_or(dimensions.get("missing")),
            "feedback": str(
                dimensions.get("feedback")
                or fallback["dimensions"]["feedback"]
            ).strip(),
        },
        "analysis": {
            "strengths": list_or(analysis.get("strengths")),
            "weaknesses": list_or(analysis.get("weaknesses")),
            "feedback": str(
                analysis.get("feedback")
                or fallback["analysis"]["feedback"]
            ).strip(),
        },
        "evidence": {
            "strengths": list_or(evidence.get("strengths")),
            "unsupported_claims": list_or(
                evidence.get("unsupported_claims")
            ),
            "feedback": str(
                evidence.get("feedback")
                or fallback["evidence"]["feedback"]
            ).strip(),
        },
        "keywords_to_add": list_or(data.get("keywords_to_add")),
        "examples_to_add": list_or(data.get("examples_to_add")),
        "strengths": list_or(data.get("strengths")),
        "improvements": list_or(data.get("improvements")),
        "word_count": word_count,
        "requested_word_limit": word_limit,
        "within_word_limit": word_count <= word_limit,
    }


def evaluate_mains_answer(
    question: str,
    answer: str,
    paper: str = "GS2",
    word_limit: int = 250,
    top_k: int = 8,
) -> Dict[str, Any]:
    """
    Evaluate a student's UPSC Mains answer.

    Sources/page metadata are used internally and never returned.
    """
    if not question or not question.strip():
        raise ValueError("Question is required.")

    if not answer or not answer.strip():
        raise ValueError("Answer is required.")

    if word_limit < 50 or word_limit > 5000:
        raise ValueError("word_limit must be between 50 and 5000.")

    demand = analyze_question_demand(
        question=question,
        selected_paper=paper,
    )

    retrieval_query = " ".join(
        [
            question.strip(),
            demand.topic,
            demand.subtopic,
            " ".join(demand.dimensions),
        ]
    )

    chunks = retrieve(
        retrieval_query,
        top_k=top_k,
    )

    context = build_context(chunks)

    demand_json = json.dumps(
        {
            "directive": demand.directive,
            "topic": demand.topic,
            "subtopic": demand.subtopic,
            "dimensions": demand.dimensions,
            "needs_balance": demand.needs_balance,
            "needs_challenges": demand.needs_challenges,
            "needs_way_forward": demand.needs_way_forward,
            "structure": demand.structure,
        },
        ensure_ascii=False,
        indent=2,
    )

    evaluator_input = f"""
QUESTION:
{question}

QUESTION DEMAND:
{demand_json}

WORD LIMIT:
{word_limit}

STUDENT ANSWER:
<student_answer>
{answer}
</student_answer>

RELEVANT CORPUS CONTEXT:
<corpus_context>
{context}
</corpus_context>

Evaluate the answer.

Important:
- Compare the answer against the question demand.
- Identify covered and missing dimensions.
- Identify factual claims that are not supported by the corpus.
- Suggest concise keywords/examples from the corpus where available.
- Do not rewrite the complete answer.
- Do not expose corpus/source/page metadata.
""".strip()

    try:
        raw = chat(
            system_prompt=EVALUATION_PROMPT,
            user_prompt=evaluator_input,
        )

        data = json.loads(_clean_json_response(raw))

        if not isinstance(data, dict):
            raise ValueError("Evaluator returned a non-object JSON result.")

        evaluation = _normalise_evaluation(
            data=data,
            answer=answer,
            word_limit=word_limit,
            demand=demand,
        )

    except Exception:
        logger.exception("Mains evaluation failed; using fallback.")
        evaluation = _fallback_evaluation(
            answer=answer,
            word_limit=word_limit,
            demand=demand,
        )

    evaluation["question_demand_analysis"] = {
        "directive": demand.directive,
        "topic": demand.topic,
        "subtopic": demand.subtopic,
        "dimensions": demand.dimensions,
        "needs_balance": demand.needs_balance,
        "needs_challenges": demand.needs_challenges,
        "needs_way_forward": demand.needs_way_forward,
        "structure": demand.structure,
    }

    return evaluation
