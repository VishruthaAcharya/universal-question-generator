import re
from typing import Any

REACTION_KEYWORDS = [
    "complete the following reaction",
    "complete the reaction",
    "identify a and b in the following",
    "identify a, b and c",
    "write the chemical equation",
    "write the reaction",
    "how is benzoyl chloride converted",
    "what happens when",
    "rosenmund",
    "cannizzaro",
    "stephen reaction",
    "clemmensen",
    "wolff-kishner",
    "aldol condensation",
    "hell-volhard-zelinsky",
    "etard reaction",
    "gatterman-koch",
    "decarboxylation",
    "tollens",
    "fehling",
    "->",
    "→",
    "convert",
]

def classify_question_type(
    question_stem: str,
    options: list[str],
    subparts: list[dict[str, Any]] | None = None,
    section_name: str = "",
    marks: int | str | None = None
) -> tuple[str, float, str]:
    """
    Classifies question type, calculates completeness score (0.0 - 1.0),
    and assigns question integrity status.
    
    Returns:
        (question_type, completeness_score, status)
    """
    stem_lower = (question_stem or "").lower().strip()
    sec_lower = (section_name or "").lower().strip()
    sub_count = len(subparts) if subparts else 0

    # 1. MCQ Detection
    if options and len(options) >= 2:
        is_subpart_question = any(opt.strip().lower().startswith(("how is", "write", "explain", "complete the", "calculate", "state", "describe", "define", "what happens")) for opt in options)
        if not is_subpart_question:
            completeness = 1.0 if len(options) >= 4 else 0.85
            return "MCQ", completeness, "COMPLETE"

    # 2. Fill in the blanks
    if "fill in" in sec_lower or "blank" in sec_lower or "______" in stem_lower or "....." in stem_lower:
        return "FILL_IN_THE_BLANK", 0.95, "COMPLETE"

    # 3. Reaction & Chemical Equation Completion
    is_explain_question = stem_lower.startswith(("explain", "describe", "define", "what is", "why is", "write the iupac", "give reason", "state", "discuss"))
    if not is_explain_question and (any(kw in stem_lower for kw in REACTION_KEYWORDS) or "complete the reaction" in stem_lower or "identify a and b" in stem_lower):
        if sub_count >= 2:
            return "LONG_ANSWER", 0.95, "COMPLETE"
        return "REACTION_COMPLETION", 0.90, "COMPLETE"

    # 4. Long Answer / Multi-part (5 marks)
    if marks in [5, "5", "5M", "5 MARKS"] or "5 mark" in sec_lower or "part d" in sec_lower or sub_count >= 2:
        return "LONG_ANSWER", 0.95, "COMPLETE"

    # 5. Short Answer (2 or 3 marks)
    if marks in [2, 3, "2", "3", "2M", "3M", "2 MARKS", "3 MARKS"] or "2 mark" in sec_lower or "part c" in sec_lower:
        return "SHORT_ANSWER", 0.90, "COMPLETE"

    # 6. Very Short Answer (1 mark non-MCQ)
    if marks in [1, "1", "1M", "1 MARK"] or "1 mark" in sec_lower or "vsa" in sec_lower:
        return "VERY_SHORT_ANSWER", 0.90, "COMPLETE"

    # 7. Default classification
    if sub_count > 0:
        return "LONG_ANSWER", 0.90, "COMPLETE"
    elif len(stem_lower) > 120:
        return "SHORT_ANSWER", 0.85, "COMPLETE"

    return "SHORT_ANSWER", 0.85, "COMPLETE"
