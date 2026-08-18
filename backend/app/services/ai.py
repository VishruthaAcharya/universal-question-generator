import json
from typing import Any
from openai import OpenAI
from app.config import settings

SYSTEM_PROMPT = """You are a question-bank generation assistant.
Generate CET-style multiple-choice questions from the supplied source material.

Rules:
- Use only information supported by the source.
- Each question has exactly four options.
- Exactly one option is correct.
- All four options must be different.
- Distractors should be plausible.
- Preserve mathematical and scientific notation.
- Difficulty must be Easy, Medium, or Hard.
- Score is 1 unless otherwise specified.
- Return ONLY JSON matching the requested schema.
"""

def _mock() -> list[dict[str, Any]]:
    return [{
        "question": "Which quantity is measured in coulombs?",
        "topic": "Electric Charges and Fields",
        "subtopic": "Electric Charge",
        "answer_1": "Electric charge",
        "answer_2": "Electric potential",
        "answer_3": "Electric field",
        "answer_4": "Resistance",
        "difficulty": "Easy",
        "correct_answer": "Electric charge",
        "score": 1,
    }]

def generate_questions(source_text: str, count: int | None = None) -> list[dict[str, Any]]:
    if not settings.openai_api_key:
        return _mock() if not count or count == 1 else (_mock() * count)

    client = OpenAI(api_key=settings.openai_api_key)
    requested = count if count and count > 0 else 10
    prompt = f"""Generate {requested} CET-style MCQs from the source below.

Return JSON only:
{{"questions":[{{"question":"...","topic":"...","subtopic":"...","answer_1":"...","answer_2":"...","answer_3":"...","answer_4":"...","difficulty":"Easy","correct_answer":"...","score":1}}]}}

SOURCE:
{source_text[:120000]}
"""

    response = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    payload = json.loads(content)
    return payload.get("questions", [])
