from typing import Any
from app.services.symbol_normalizer import normalize_math_and_greek_symbols, detect_unresolved_corruption

def audit_and_validate_question(q: dict[str, Any]) -> dict[str, Any]:
    """
    Audits an extracted question for:
    1. Clean math/Greek symbol normalization across question stem, options, and answer.
    2. MCQ option count validation (exactly 4 options for 4-choice MCQs).
    3. Correct Answer correspondence check against extracted options.
    4. Unresolved corruption / unreadable artifact detection.
    5. Evidence-based granular confidence scoring.
    """
    # 1. Normalize Unicode symbols
    stem = normalize_math_and_greek_symbols(q.get("question", "") or "")
    q["question"] = stem

    raw_options = q.get("options", [])
    normalized_options = [normalize_math_and_greek_symbols(str(opt)) for opt in raw_options if opt is not None]
    q["options"] = normalized_options

    if len(normalized_options) >= 4:
        q["option_a"] = normalized_options[0]
        q["option_b"] = normalized_options[1]
        q["option_c"] = normalized_options[2]
        q["option_d"] = normalized_options[3]
    elif len(normalized_options) == 3:
        q["option_a"] = normalized_options[0]
        q["option_b"] = normalized_options[1]
        q["option_c"] = normalized_options[2]
        q["option_d"] = ""
    elif len(normalized_options) == 2:
        q["option_a"] = normalized_options[0]
        q["option_b"] = normalized_options[1]
        q["option_c"] = ""
        q["option_d"] = ""

    ans = normalize_math_and_greek_symbols(str(q.get("correct_answer", "") or q.get("source_answer", "") or "")).strip()
    if ans:
        q["correct_answer"] = ans

    q_type = q.get("question_type", "MCQ")
    defects = []

    # 2. Corruption checks
    stem_defects = detect_unresolved_corruption(stem)
    if stem_defects:
        defects.extend([f"Question stem: {d}" for d in stem_defects])

    for idx, opt in enumerate(normalized_options):
        opt_defects = detect_unresolved_corruption(opt)
        if opt_defects:
            defects.extend([f"Option {chr(65 + idx)}: {d}" for d in opt_defects])

    # 3. MCQ 4-Option Integrity Check
    option_confidence = 1.0
    if q_type == "MCQ":
        if len(normalized_options) != 4:
            defects.append(f"MCQ has {len(normalized_options)} options instead of exactly 4 options.")
            option_confidence = 0.60
        else:
            # Check for empty or duplicate options
            unique_opts = set(o.strip().lower() for o in normalized_options if o.strip())
            if len(unique_opts) < 4:
                defects.append("Duplicate or empty options detected among 4 MCQ choices.")
                option_confidence = 0.65

    # 4. Correct Answer Correspondence Check
    answer_confidence = 0.95 if ans else 0.0
    if q_type == "MCQ" and ans:
        ans_upper = ans.upper()
        # Valid if letter A/B/C/D or exact match with one of the option texts
        is_letter_match = ans_upper in ["A", "B", "C", "D", "OPTION A", "OPTION B", "OPTION C", "OPTION D", "(A)", "(B)", "(C)", "(D)", "1", "2", "3", "4"]
        is_text_match = any(ans.lower() == opt.lower().strip() for opt in normalized_options)
        
        if not (is_letter_match or is_text_match):
            defects.append(f"Correct answer '{ans}' does not correspond to any of the 4 extracted options.")
            answer_confidence = 0.50

    # 5. Question Stem Confidence
    question_confidence = 0.98 if len(stem) >= 10 else 0.70
    if stem_defects:
        question_confidence = min(question_confidence, 0.60)

    # 6. Overall Confidence Calculation
    if q_type == "MCQ":
        overall_conf = round(0.4 * question_confidence + 0.35 * option_confidence + 0.25 * answer_confidence, 3)
    else:
        overall_conf = round(0.6 * question_confidence + 0.4 * (answer_confidence if ans else 0.9), 3)

    q["question_confidence"] = question_confidence
    q["option_confidence"] = option_confidence
    q["answer_confidence"] = answer_confidence
    q["overall_confidence"] = overall_conf

    if defects:
        q["status"] = "REVIEW_REQUIRED"
        q["extraction_defects"] = defects
        q["review_reason"] = "; ".join(defects)
    else:
        q["status"] = "COMPLETE"
        q["extraction_defects"] = []
        q["review_reason"] = "All integrity and Unicode checks passed."

    return q
