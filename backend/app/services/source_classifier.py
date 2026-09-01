import re
from typing import Any
from app.services.deterministic_parser import QUESTION_HEADER_PATTERN, OPTION_START_PATTERN, ANSWER_PATTERN
from app.services.answer_key_detector import (
    ANSWER_KEY_HEADING_PATTERNS,
    DISCRETE_ENTRY_PATTERN,
    COMPACT_ENTRY_PATTERN,
    RANGE_GROUPED_PATTERN,
    is_answer_key_text
)

# Reference indicators
REFERENCE_KEYWORDS = [
    "periodic table", "formula sheet", "list of constants",
    "read the following passage", "instructions:", "useful information",
    "reference material", "equation sheet", "formulae"
]

def classify_page_content(
    text: str,
    page_number: int,
    filename: str | None = None,
    is_dataframe: bool = False
) -> dict[str, Any]:
    """
    Classifies a single page/section's text content into one of the source roles:
    QUESTION_SOURCE, ANSWER_SOURCE, MIXED_SOURCE, REFERENCE_SOURCE, UNKNOWN_SOURCE.
    
    Considers headings, option density, numbering structure, question keywords,
    answer keywords, and filename as a weak indicator.
    """
    if not text or not text.strip():
        return {
            "role": "UNKNOWN_SOURCE",
            "confidence_score": 0.0,
            "confidence_label": "LOW",
            "question_numbers": [],
            "answer_numbers": []
        }

    clean_text = text.strip()
    lines = [l.strip() for l in clean_text.splitlines() if l.strip()]
    
    # 1. Parse question and answer numbers
    q_matches = list(QUESTION_HEADER_PATTERN.finditer(clean_text))
    question_numbers = []
    for m in q_matches:
        match_str = m.group(0).strip()
        num_m = re.search(r"\d+", match_str)
        if num_m:
            question_numbers.append(int(num_m.group(0)))

    a_matches = list(DISCRETE_ENTRY_PATTERN.finditer(clean_text))
    answer_numbers = []
    for m in a_matches:
        num_str = m.group(1).strip()
        if num_str.isdigit():
            answer_numbers.append(int(num_str))

    # 2. Filename Clues (Weak indicator only)
    fn_lower = (filename or "").lower()
    fn_is_answers = any(w in fn_lower for w in ["answer", "key", "solution", "sol"])
    fn_is_questions = any(w in fn_lower for w in ["question", "exam", "paper", "test", "quiz", "task"])

    # 3. Dataframe Tabular Classification
    if is_dataframe:
        # Check column names in dataframe representation
        has_question_col = any(w in clean_text.lower() for w in ["question", "stem", "prompt", "problem"])
        has_answer_col = any(w in clean_text.lower() for w in ["answer", "correct", "solution", "key"])
        
        if has_question_col and has_answer_col:
            role = "MIXED_SOURCE"
            score = 0.95
        elif has_question_col:
            role = "QUESTION_SOURCE"
            score = 0.95
        elif has_answer_col:
            role = "ANSWER_SOURCE"
            score = 0.95
        else:
            role = "UNKNOWN_SOURCE"
            score = 0.50

        return {
            "role": role,
            "confidence_score": score,
            "confidence_label": "HIGH" if score >= 0.90 else "MEDIUM",
            "question_numbers": sorted(list(set(question_numbers))),
            "answer_numbers": sorted(list(set(answer_numbers)))
        }

    # 4. Check Explicit Answer Key Heading
    has_explicit_answer_heading = False
    for line in lines[:5]:  # Look at the first 5 lines for a header
        if any(pat.search(line) for pat in ANSWER_KEY_HEADING_PATTERNS):
            has_explicit_answer_heading = True
            break

    # Check for inline answers (e.g. "Answer: B")
    has_inline_answers = len(ANSWER_PATTERN.findall(clean_text)) >= max(1, len(q_matches) * 0.5)

    # 5. Check if is_answer_key_text
    is_ak = is_answer_key_text(clean_text)

    # 6. Check Reference Keywords
    has_reference_keywords = any(kw in clean_text.lower() for kw in REFERENCE_KEYWORDS)

    # 7. Classification Decision Logic
    role = "UNKNOWN_SOURCE"
    score = 0.50

    if is_ak:
        if len(q_matches) >= 3 and has_inline_answers:
            role = "MIXED_SOURCE"
            score = 0.90
        else:
            role = "ANSWER_SOURCE"
            score = 0.95 if has_explicit_answer_heading else 0.85
    elif has_explicit_answer_heading:
        role = "ANSWER_SOURCE"
        score = 0.98
    elif len(q_matches) >= 1:
        # It has questions!
        if has_inline_answers:
            role = "MIXED_SOURCE"
            score = 0.88
        else:
            role = "QUESTION_SOURCE"
            score = 0.92
    elif has_reference_keywords:
        role = "REFERENCE_SOURCE"
        score = 0.80
    else:
        # Check if file is an image
        is_image_file = bool(filename and any(filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]))
        if is_image_file:
            if fn_is_answers and not fn_is_questions:
                role = "ANSWER_SOURCE"
                score = 0.85
            else:
                role = "QUESTION_SOURCE"
                score = 0.85
        # Weak fallback using filename clues
        elif fn_is_answers and not fn_is_questions:
            role = "ANSWER_SOURCE"
            score = 0.60
        elif fn_is_questions and not fn_is_answers:
            role = "QUESTION_SOURCE"
            score = 0.60
        else:
            role = "UNKNOWN_SOURCE"
            score = 0.30

    # Boost confidence slightly if filename matches role
    if role == "ANSWER_SOURCE" and fn_is_answers:
        score = min(1.0, score + 0.05)
    elif role == "QUESTION_SOURCE" and fn_is_questions:
        score = min(1.0, score + 0.05)

    # Determine confidence label
    if score >= 0.90:
        label = "HIGH"
    elif score >= 0.70:
        label = "MEDIUM"
    else:
        label = "LOW"

    return {
        "role": role,
        "confidence_score": round(score, 2),
        "confidence_label": label,
        "question_numbers": sorted(list(set(question_numbers))),
        "answer_numbers": sorted(list(set(answer_numbers)))
    }
