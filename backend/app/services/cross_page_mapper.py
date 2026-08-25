import re
from typing import Any
from app.config import settings

def extract_leading_question_number(stem: str) -> int | str | None:
    """Extracts leading question number from question stem if not already populated."""
    if not stem:
        return None
    
    m = re.match(r"^(?:(?:Q(?:uestion)?[\s\.\:\-]*)|\[|\()?(\d+)[\]\)\.\:\-\s]", stem.strip(), re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return m.group(1)
    return None

def map_cross_page_answers(
    questions: list[dict[str, Any]],
    answer_key_entries: list[dict[str, Any]],
    context: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Deterministically maps cross-page Answer Key entries to Question objects based on the preferred hierarchy.
    """
    if not questions:
        return []

    # If no answer key entries detected at all
    if not answer_key_entries:
        for idx, q in enumerate(questions, start=1):
            inline_ans = q.get("correct_answer")
            if inline_ans and str(inline_ans).strip():
                # Preserve inline answer extracted directly from question stem
                q["source_answer"] = str(inline_ans).strip()
                q["answer_source"] = "QUESTION_TEXT"
                q["answer_page"] = q.get("source_page")
                q["mapping_confidence"] = 0.95
                q["answer_mapping_status"] = "ANSWER_MAPPED"
                q["mapping_reason"] = "Answer extracted inline from question block."
            else:
                q["source_answer"] = None
                q["answer_source"] = "MISSING"
                q["answer_page"] = None
                q["mapping_confidence"] = 0.0
                q["answer_mapping_status"] = "MISSING_ANSWER"
                q["mapping_reason"] = "No answer key detected in source document."
        return questions

    # Group answer key entries by question_number and chapter
    # Structure: { question_num: [entry1, entry2, ...] }
    entries_by_num: dict[Any, list[dict[str, Any]]] = {}
    for entry in answer_key_entries:
        q_num = entry.get("question_number")
        if q_num is not None:
            entries_by_num.setdefault(q_num, []).append(entry)

    # Track matched answer key entries
    matched_entry_indices = set()

    for idx, q in enumerate(questions, start=1):
        q_stem = q.get("question", "") or ""
        q_num = q.get("question_number")
        if q_num is None:
            q_num = extract_leading_question_number(q_stem) or idx
            q["question_number"] = q_num

        q_id = q.get("question_id") or f"Q_{idx:03d}"
        q["question_id"] = q_id
        q["question_index"] = idx - 1

        q_chapter = str(q.get("source_chapter") or q.get("topic") or "").lower().strip()
        q_section = str(q.get("source_section") or "").lower().strip()
        q_page = q.get("source_page")

        candidates = entries_by_num.get(q_num, [])

        if not candidates:
            # Check string / int variations
            if isinstance(q_num, int):
                candidates = entries_by_num.get(str(q_num), []) or entries_by_num.get(f"Q{q_num}", [])
            elif isinstance(q_num, str) and q_num.isdigit():
                candidates = entries_by_num.get(int(q_num), [])

        # Priority 1: Unique Exact Question Number Match
        if len(candidates) == 1:
            matched_entry = candidates[0]
            ans_val = matched_entry.get("answer")
            ans_page = matched_entry.get("source_page")
            ans_sec = matched_entry.get("source_section", "Answer Key")

            q["correct_answer"] = ans_val
            q["source_answer"] = ans_val
            q["answer_source"] = matched_entry.get("source_type", "EXPLICIT_ANSWER_KEY")
            q["answer_page"] = ans_page
            q["answer_section"] = ans_sec
            q["mapping_confidence"] = 0.99
            q["answer_mapping_status"] = "ANSWER_MAPPED"
            q["mapping_reason"] = f"Explicit question-number match (Q{q_num} → Answer {ans_val} on page {ans_page})."

        # Priority 2: Repeated Question Numbers Disambiguated by Chapter/Section
        elif len(candidates) > 1:
            best_match = None
            for cand in candidates:
                cand_chap = str(cand.get("source_chapter") or "").lower().strip()
                cand_sec = str(cand.get("source_section") or "").lower().strip()
                if cand_chap and q_chapter and (cand_chap in q_chapter or q_chapter in cand_chap):
                    best_match = cand
                    break
                if cand_sec and q_section and (cand_sec in q_section or q_section in cand_sec):
                    best_match = cand
                    break

            if best_match:
                ans_val = best_match.get("answer")
                ans_page = best_match.get("source_page")
                q["correct_answer"] = ans_val
                q["source_answer"] = ans_val
                q["answer_source"] = best_match.get("source_type", "EXPLICIT_ANSWER_KEY")
                q["answer_page"] = ans_page
                q["answer_section"] = best_match.get("source_section", "Answer Key")
                q["mapping_confidence"] = 0.95
                q["answer_mapping_status"] = "ANSWER_MAPPED"
                q["mapping_reason"] = f"Chapter/section disambiguated match (Q{q_num} in {best_match.get('source_chapter')} → {ans_val} on page {ans_page})."
            else:
                # Ambiguous repeated question numbers across sections without distinct chapter info
                # Do NOT guess or silently map!
                q["correct_answer"] = candidates[0].get("answer")
                q["source_answer"] = candidates[0].get("answer")
                q["answer_source"] = "EXPLICIT_ANSWER_KEY"
                q["answer_page"] = candidates[0].get("source_page")
                q["mapping_confidence"] = 0.63
                q["answer_mapping_status"] = "AMBIGUOUS_MAPPING"
                q["review_required"] = True
                q["mapping_reason"] = f"Multiple answer key entries detected for question #{q_num}. Human Review required."

        # Priority 3: Fallback Sequential Mapping
        elif not candidates and len(answer_key_entries) == len(questions):
            # 1-to-1 sequential mapping
            seq_entry = answer_key_entries[idx - 1]
            ans_val = seq_entry.get("answer")
            ans_page = seq_entry.get("source_page")

            q["correct_answer"] = ans_val
            q["source_answer"] = ans_val
            q["answer_source"] = "EXPLICIT_ANSWER_KEY"
            q["answer_page"] = ans_page
            q["answer_section"] = seq_entry.get("source_section", "Answer Key")
            q["mapping_confidence"] = 0.88
            q["answer_mapping_status"] = "ANSWER_MAPPED"
            q["mapping_reason"] = f"Sequential 1-to-1 document order match (Item #{idx} → {ans_val} on page {ans_page})."

        # Priority 4: No matching answer key entry found (Partial answer key)
        else:
            inline_ans = q.get("correct_answer")
            if inline_ans and str(inline_ans).strip():
                q["source_answer"] = str(inline_ans).strip()
                q["answer_source"] = "QUESTION_TEXT"
                q["answer_page"] = q.get("source_page")
                q["mapping_confidence"] = 0.95
                q["answer_mapping_status"] = "ANSWER_MAPPED"
                q["mapping_reason"] = "Answer extracted inline from question block."
            else:
                q["source_answer"] = None
                q["answer_source"] = "MISSING"
                q["answer_page"] = None
                q["mapping_confidence"] = 0.0
                q["answer_mapping_status"] = "MISSING_ANSWER"
                q["mapping_reason"] = f"Question #{q_num} is not present in the detected answer key."

    return questions
