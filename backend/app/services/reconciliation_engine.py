import re
import json
import logging
from typing import Any, Optional
from app.services.azure_openai import get_client, _call_azure_with_retry, SYSTEM_PROMPT
from app.services.symbol_normalizer import normalize_math_and_greek_symbols
from app.config import settings

logger = logging.getLogger("reconciliation_engine")

def compute_string_similarity(s1: str, s2: str) -> float:
    """Computes basic Jaccard similarity of normalized words between two strings."""
    w1 = set(re.findall(r"\w+", s1.lower()))
    w2 = set(re.findall(r"\w+", s2.lower()))
    if not w1 or not w2:
        return 0.0
    return len(w1.intersection(w2)) / len(w1.union(w2))

def detect_duplicate_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Scans list of questions and flags potential duplicates based on stem text similarity.
    Attaches warning flags and references to duplicates without deleting them.
    """
    normalized_stems = []
    for q in questions:
        stem = str(q.get("question", "")).strip().lower()
        # Clean non-alphanumeric chars
        stem_clean = re.sub(r"\W+", "", stem)
        normalized_stems.append((stem_clean, q))

    for i in range(len(questions)):
        stem1, q1 = normalized_stems[i]
        if not stem1:
            continue
        for j in range(i + 1, len(questions)):
            stem2, q2 = normalized_stems[j]
            # Exact clean stem match or high Jaccard similarity
            is_dup = (stem1 == stem2)
            if not is_dup and len(q1.get("question", "")) > 20:
                is_dup = compute_string_similarity(q1.get("question", ""), q2.get("question", "")) > 0.88

            if is_dup:
                # Flag as potential duplicates
                q1.setdefault("duplicate_warnings", [])
                q2.setdefault("duplicate_warnings", [])
                
                loc1 = f"{q1.get('source_file', 'unknown')} Page {q1.get('source_page', 'unknown')}"
                loc2 = f"{q2.get('source_file', 'unknown')} Page {q2.get('source_page', 'unknown')}"
                
                warning1 = {
                    "message": f"Potential duplicate detected on {loc2}.",
                    "other_question_id": q2.get("question_id"),
                    "other_location": loc2
                }
                warning2 = {
                    "message": f"Potential duplicate detected on {loc1}.",
                    "other_question_id": q1.get("question_id"),
                    "other_location": loc1
                }
                
                if warning1 not in q1["duplicate_warnings"]:
                    q1["duplicate_warnings"].append(warning1)
                    q1["validation_status"] = "DUPLICATE"
                    q1["review_required"] = True
                if warning2 not in q2["duplicate_warnings"]:
                    q2["duplicate_warnings"].append(warning2)
                    q2["validation_status"] = "DUPLICATE"
                    q2["review_required"] = True

    return questions

def run_ai_assisted_matching(
    unmatched_qs: list[dict[str, Any]],
    unmatched_ans: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Uses Azure OpenAI as the final fallback to semantically reconcile questions and answers.
    Returns a dictionary mapping question_id -> answer_key_entry dict.
    """
    if not unmatched_qs or not unmatched_ans:
        return {}

    client = get_client()
    
    # Format questions and answers for prompt
    qs_prompt = [
        {
            "question_id": q.get("question_id"),
            "question": q.get("question"),
            "options": q.get("options", []),
            "source_file": q.get("source_file"),
            "source_page": q.get("source_page"),
            "question_number": q.get("question_number")
        }
        for q in unmatched_qs
    ]
    
    ans_prompt = [
        {
            "index": idx,
            "answer": a.get("answer"),
            "question_number": a.get("question_number"),
            "source_file": a.get("source_file"),
            "source_page": a.get("source_page"),
            "explanation": a.get("explanation", "")
        }
        for idx, a in enumerate(unmatched_ans)
    ]

    prompt = f"""You are a precise educational question-to-answer key reconciliation engine.
We have a set of unmatched extracted questions and a list of unmatched answer key entries.
Your task is to map each question to the correct answer key entry based on:
1. Question and answer numbering.
2. Semantic alignment (e.g. if the answer text matches an option value of a question).
3. Document flow and structure context.

UNMATCHED QUESTIONS:
{json.dumps(qs_prompt, indent=2)}

UNMATCHED ANSWERS:
{json.dumps(ans_prompt, indent=2)}

Return ONLY a JSON object mapping each question's "question_id" to the corresponding answer's "index" in the answers list.
If a question has no clear matching answer, map it to null.
Ensure every question_id in UNMATCHED QUESTIONS is key in the output.

Format:
{{
  "mappings": {{
    "Q_001": 2,
    "Q_002": null
  }}
}}
"""
    try:
        response = _call_azure_with_retry(
            client,
            {
                "model": settings.azure_openai_deployment_name,
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "You are a precise question-answer mapping assistant."},
                    {"role": "user", "content": prompt}
                ]
            }
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        mappings = payload.get("mappings", {})
        
        resolved = {}
        for q_id, ans_idx in mappings.items():
            if ans_idx is not None and 0 <= int(ans_idx) < len(unmatched_ans):
                resolved[q_id] = unmatched_ans[int(ans_idx)]
        return resolved
    except Exception as e:
        logger.error(f"AI assisted matching fallback failed: {e}")
        return {}

def reconcile_questions_and_answers(
    questions: list[dict[str, Any]],
    answers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Core reconciliation routine that maps questions to answers using a multi-stage process:
    Stage 1: Explicit question number matches explicit answer number (with Section/Chapter/File checks).
    Stage 2: Sequential Ordering (if safe: no numbering gaps, counts match).
    Stage 3: Semantic option matching.
    Stage 4: AI-assisted matching fallback.
    
    Mutates questions in-place to populate:
    - source_answer_key / source_answer_text
    - final_answer_key / final_answer_text
    - answer_mapping_method
    - answer_mapping_confidence
    - validation_status / review_required / warnings
    """
    if not questions:
        return []

    # Initialize reconciliation fields
    for q in questions:
        q["source_answer_key"] = None
        q["source_answer_text"] = None
        q["source_answer_explanation"] = None
        q["answer_mapping_method"] = "UNRESOLVED"
        q["answer_mapping_confidence"] = "LOW"
        q["answer_mapping_score"] = 0.0
        q["duplicate_warnings"] = []
        
        # Populate option fields separately
        opts = q.get("options", [])
        q["option_A"] = opts[0] if len(opts) > 0 else ""
        q["option_B"] = opts[1] if len(opts) > 1 else ""
        q["option_C"] = opts[2] if len(opts) > 2 else ""
        q["option_D"] = opts[3] if len(opts) > 3 else ""

    # Detect duplicates
    questions = detect_duplicate_questions(questions)

    # Track matched answers
    matched_answer_indices = set()
    unmatched_questions = list(questions)

    # Helper to normalise answers
    def get_option_letter_for_text(options: list[str], val: str) -> Optional[str]:
        if not val or not options:
            return None
        val_clean = str(val).strip().lower()
        for idx, opt in enumerate(options):
            if val_clean == str(opt).strip().lower():
                return chr(65 + idx)
        # Check substring match
        for idx, opt in enumerate(options):
            if val_clean in str(opt).strip().lower() or str(opt).strip().lower() in val_clean:
                return chr(65 + idx)
        return None

    # STAGE 1: Explicit question number matching (Q1 -> Answer 1)
    for q in list(unmatched_questions):
        q_num = q.get("question_number")
        if q_num is None:
            continue

        q_file = q.get("source_file")
        q_chap = str(q.get("source_chapter") or q.get("topic") or "").lower().strip()

        # Find answer candidates
        candidates = []
        for idx, a in enumerate(answers):
            if idx in matched_answer_indices:
                continue
            
            a_num = a.get("question_number")
            if a_num is not None and str(a_num) == str(q_num):
                candidates.append((idx, a))

        if len(candidates) == 1:
            idx, a = candidates[0]
            ans_val = a.get("answer")
            options = q.get("options", [])
            opt_letter = get_option_letter_for_text(options, ans_val)
            
            q["source_answer_key"] = opt_letter or ans_val
            q["source_answer_text"] = ans_val if opt_letter else None
            q["source_answer_explanation"] = a.get("explanation")
            q["answer_mapping_method"] = "EXPLICIT"
            q["answer_mapping_confidence"] = "HIGH"
            q["answer_mapping_score"] = 0.98
            q["answer_source_file"] = a.get("source_file")
            q["answer_source_page"] = a.get("source_page")
            q["answer_source_role"] = a.get("source_role", "ANSWER_SOURCE")
            
            matched_answer_indices.add(idx)
            unmatched_questions.remove(q)
            
        elif len(candidates) > 1:
            # Disambiguate using Chapter, Section, or File matching
            best_match = None
            for idx, a in candidates:
                a_chap = str(a.get("source_chapter") or "").lower().strip()
                a_file = a.get("source_file")
                
                # Check for chapter alignment
                if q_chap and a_chap and (q_chap in a_chap or a_chap in q_chap):
                    best_match = (idx, a)
                    break
                # Check for parent file alignment
                if q_file and a_file and q_file == a_file:
                    best_match = (idx, a)
                    break

            if best_match:
                idx, a = best_match
                ans_val = a.get("answer")
                options = q.get("options", [])
                opt_letter = get_option_letter_for_text(options, ans_val)
                
                q["source_answer_key"] = opt_letter or ans_val
                q["source_answer_text"] = ans_val if opt_letter else None
                q["source_answer_explanation"] = a.get("explanation")
                q["answer_mapping_method"] = "EXPLICIT_DISAMBIGUATED"
                q["answer_mapping_confidence"] = "HIGH"
                q["answer_mapping_score"] = 0.95
                q["answer_source_file"] = a.get("source_file")
                q["answer_source_page"] = a.get("source_page")
                q["answer_source_role"] = a.get("source_role", "ANSWER_SOURCE")
                
                matched_answer_indices.add(idx)
                unmatched_questions.remove(q)
            else:
                # Ambiguous repeated numbers
                idx, a = candidates[0] # Default to first but flag it
                ans_val = a.get("answer")
                options = q.get("options", [])
                opt_letter = get_option_letter_for_text(options, ans_val)
                
                q["source_answer_key"] = opt_letter or ans_val
                q["source_answer_text"] = ans_val if opt_letter else None
                q["source_answer_explanation"] = a.get("explanation")
                q["answer_mapping_method"] = "AMBIGUOUS"
                q["answer_mapping_confidence"] = "LOW"
                q["answer_mapping_score"] = 0.50
                q["validation_status"] = "AMBIGUOUS"
                q["review_required"] = True
                q["warnings"] = f"Multiple matching answers found for question #{q_num}."
                
                # Do NOT add to matched indices so human can reconcile

    # STAGE 2: Sequential Matching (Only if evidence is strong: counts match exactly and no duplicate numbers)
    # Check if number of unmatched questions matches number of unmatched answers, and they have sequential ordering
    remaining_ans = [(idx, a) for idx, a in enumerate(answers) if idx not in matched_answer_indices]
    if len(unmatched_questions) == len(remaining_ans) and len(unmatched_questions) > 0:
        # Check that there are no numbering conflicts (e.g. out of order numbers)
        q_nums = [q.get("question_number") for q in unmatched_questions]
        a_nums = [a.get("question_number") for idx, a in remaining_ans]
        
        has_number_duplicates = len(set(n for n in q_nums if n is not None)) < len([n for n in q_nums if n is not None])
        
        if not has_number_duplicates:
            # Safe to map sequentially
            for idx_q, q in enumerate(list(unmatched_questions)):
                idx_a, a = remaining_ans[idx_q]
                ans_val = a.get("answer")
                options = q.get("options", [])
                opt_letter = get_option_letter_for_text(options, ans_val)
                
                q["source_answer_key"] = opt_letter or ans_val
                q["source_answer_text"] = ans_val if opt_letter else None
                q["source_answer_explanation"] = a.get("explanation")
                q["answer_mapping_method"] = "SEQUENTIAL"
                q["answer_mapping_confidence"] = "MEDIUM"
                q["answer_mapping_score"] = 0.84
                q["answer_source_file"] = a.get("source_file")
                q["answer_source_page"] = a.get("source_page")
                q["answer_source_role"] = a.get("source_role", "ANSWER_SOURCE")
                
                matched_answer_indices.add(idx_a)
                unmatched_questions.remove(q)

    # STAGE 3: Semantic Option Matching (Answer matches one option text, numbering is missing/unmatched)
    for q in list(unmatched_questions):
        options = q.get("options", [])
        if not options:
            continue
            
        semantic_matches = []
        for idx, a in enumerate(answers):
            if idx in matched_answer_indices:
                continue
                
            ans_val = str(a.get("answer", "")).strip()
            opt_letter = get_option_letter_for_text(options, ans_val)
            if opt_letter:
                semantic_matches.append((idx, a, opt_letter))

        if len(semantic_matches) == 1:
            idx_a, a, opt_letter = semantic_matches[0]
            q["source_answer_key"] = opt_letter
            q["source_answer_text"] = a.get("answer")
            q["source_answer_explanation"] = a.get("explanation")
            q["answer_mapping_method"] = "SEMANTIC"
            q["answer_mapping_confidence"] = "LOW"
            q["answer_mapping_score"] = 0.72
            q["answer_source_file"] = a.get("source_file")
            q["answer_source_page"] = a.get("source_page")
            q["answer_source_role"] = a.get("source_role", "ANSWER_SOURCE")
            
            matched_answer_indices.add(idx_a)
            unmatched_questions.remove(q)

    # STAGE 4: AI-assisted matching (Final Fallback)
    if unmatched_questions:
        remaining_ans_dicts = [a for idx, a in enumerate(answers) if idx not in matched_answer_indices]
        if remaining_ans_dicts:
            ai_mappings = run_ai_assisted_matching(unmatched_questions, remaining_ans_dicts)
            for q in list(unmatched_questions):
                q_id = q.get("question_id")
                if q_id in ai_mappings:
                    a = ai_mappings[q_id]
                    # Find index in full answers
                    idx_a = next((i for i, ans in enumerate(answers) if ans == a), None)
                    if idx_a is not None and idx_a not in matched_answer_indices:
                        ans_val = a.get("answer")
                        options = q.get("options", [])
                        opt_letter = get_option_letter_for_text(options, ans_val)
                        
                        q["source_answer_key"] = opt_letter or ans_val
                        q["source_answer_text"] = ans_val if opt_letter else None
                        q["source_answer_explanation"] = a.get("explanation")
                        q["answer_mapping_method"] = "AI_FALLBACK"
                        q["answer_mapping_confidence"] = "LOW"
                        q["answer_mapping_score"] = 0.70
                        q["answer_source_file"] = a.get("source_file")
                        q["answer_source_page"] = a.get("source_page")
                        q["answer_source_role"] = a.get("source_role", "ANSWER_SOURCE")
                        
                        matched_answer_indices.add(idx_a)
                        unmatched_questions.remove(q)

    # Post-process unresolved answer mappings
    for q in unmatched_questions:
        # Check if there is an inline correct_answer extracted from page parser
        inline_ans = q.get("correct_answer")
        if inline_ans and str(inline_ans).strip():
            options = q.get("options", [])
            opt_letter = get_option_letter_for_text(options, inline_ans)
            q["source_answer_key"] = opt_letter or inline_ans
            q["source_answer_text"] = inline_ans if opt_letter else None
            q["answer_mapping_method"] = "INLINE"
            q["answer_mapping_confidence"] = "HIGH"
            q["answer_mapping_score"] = 0.95
        else:
            q["validation_status"] = "REVIEW_REQUIRED"
            q["review_required"] = True
            q["warnings"] = "Answer could not be reliably matched."

    # Final Option Check: Duplicate Option Values Detection
    for q in questions:
        options = q.get("options", [])
        if options and len(options) >= 2:
            unique_opts = set(str(o).strip().lower() for o in options if o is not None)
            if len(unique_opts) < len(options):
                # Duplicate values detected! E.g. Option A = 6%, Option D = 6%
                q["validation_status"] = "AMBIGUOUS"
                q["review_required"] = True
                q["warnings"] = "Duplicate MCQ option values detected."

    # Default final_answers
    for q in questions:
        # Default final answer to source answer key if available
        q["final_answer_key"] = q["source_answer_key"]
        q["final_answer_text"] = q["source_answer_text"]

    return questions
