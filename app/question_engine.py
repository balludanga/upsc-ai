# app/question_engine.py

from typing import List, Dict, Any
import json
import re

DIRECTIVES = {
    "discuss",
    "explain",
    "examine",
    "analyse",
    "analyze",
    "evaluate",
    "critically examine",
    "comment",
    "elaborate",
    "justify",
    "assess",
}


QUESTION_ANALYSIS_PROMPT = """
You are a UPSC question-demand analyzer.

Analyze the question and return ONLY valid JSON.

Identify:
1. paper
2. directive
3. topic
4. subtopic
5. dimensions
6. whether balanced analysis is required
7. whether challenges are required
8. whether way forward is appropriate
9. required answer structure

JSON:
{
  "paper": "GS1/GS2/GS3/GS4/ESSAY/OPTIONAL",
  "directive": "",
  "topic": "",
  "subtopic": "",
  "dimensions": [],
  "needs_balance": false,
  "needs_challenges": false,
  "needs_way_forward": false,
  "structure": []
}

Do not invent factual information.
"""


def analyze_question(question: str, chat_fn) -> Dict[str, Any]:
    response = chat_fn(
        QUESTION_ANALYSIS_PROMPT,
        question,
    )

    cleaned = response.strip()

    cleaned = re.sub(
        r"^```json\s*|\s*```$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "paper": "GENERAL",
            "directive": "discuss",
            "topic": question,
            "subtopic": "",
            "dimensions": [],
            "needs_balance": False,
            "needs_challenges": True,
            "needs_way_forward": True,
            "structure": [
                "Introduction",
                "Main Body",
                "Challenges",
                "Way Forward",
                "Conclusion",
            ],
        }

    return data