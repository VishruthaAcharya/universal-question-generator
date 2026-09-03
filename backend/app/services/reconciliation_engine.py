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

def normalize_group_key(val: str | None) -> str:
    """Normalizes section/chapter/image/file headers to extract canonical group identity."""
    if not val:
        return ""
    s = str(val).strip().lower()
    s = re.sub(r"\.[a-zA-Z0-9]+$", "", s)
    s = re.sub(r"^(?:question[\s_\-]*)?(?:image|img|file|page|section|part|chapter|test|set|paper|group)[\s_\-]*", "group_", s)
    m = re.search(r"(?:group_|#|\b)([a-z0-9]+)\b", s)
    if m:
        return m.group(1).lower()
    return re.sub(r"[^a-z0-9]", "", s)

def are_groups_compatible(q_group: str | None, a_group: str | None, q_file: str | None = None, a_file: str | None = None) -> bool:
    """
    Checks if a question group/file is compatible with an answer key group/file.
    Returns True if either group is unspecified or if they share group tokens/numbers.
    """
    if not q_group and not q_file and not a_group:
        return True

    q_keys = set()
    for item in (q_group, q_file):
        if item:
            clean = str(item).strip().lower()
            q_keys.add(clean)
            q_keys.add(re.sub(r"[^a-z0-9]", "", clean))
            norm = normalize_group_key(clean)
            if norm:
                q_keys.add(norm)
            nums = re.findall(r"\d+", clean)
            for n in nums:
                q_keys.add(n)
                q_keys.add(f"image{n}")
                q_keys.add(f"image_{n}")
                q_keys.add(f"image {n}")

    a_keys = set()
    for item in (a_group, a_file):
        if item:
            clean = str(item).strip().lower()
            a_keys.add(clean)
            a_keys.add(re.sub(r"[^a-z0-9]", "", clean))
            norm = normalize_group_key(clean)
            if norm:
                a_keys.add(norm)
            nums = re.findall(r"\d+", clean)
            for n in nums:
                a_keys.add(n)
                a_keys.add(f"image{n}")
                a_keys.add(f"image_{n}")
                a_keys.add(f"image {n}")

    if not q_keys or not a_keys:
        return True

    if q_keys.intersection(a_keys):
        return True

    for qk in q_keys:
        for ak in a_keys:
            if len(qk) >= 2 and len(ak) >= 2 and (qk in ak or ak in qk):
                return True

    return False

def reconcile_questions_and_answers(
    questions: list[dict[str, Any]],
    answers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Core reconciliation routine that maps questions to answers using a multi-stage process:
    Stage 1: Explicit question number matches explicit answer number (with Section/Chapter/Image Group checks).
    Stage 2: Sequential Ordering (if safe: within same group, no numbering gaps, counts match).
    Stage 3: Semantic option matching (within compatible group).
    Stage 4: AI-assisted matching fallback.
    
    Mutates questions in-place to populate:
    - question_source_image / question_group
    - answer_source_image / answer_key_group
    - question_number
    - source_answer_key / source_answer_text
    - final_answer_key / final_answer_text
    - mapping_method / mapping_confidence / answer_mapping_score
    - validation_status / review_required / warnings
    """
    if not questions:
        return []

    # Initialize reconciliation and provenance fields
    for q in questions:
        q_file = q.get("source_file") or q.get("question_source_image") or ""
        q["question_source_image"] = q_file
        q["question_group"] = q.get("question_group") or q_file
        q["answer_source_image"] = None
        q["answer_key_group"] = None
        q["source_answer_key"] = None
        q["source_answer_text"] = None
        q["source_answer_explanation"] = None
        q["answer_mapping_method"] = "UNRESOLVED"
        q["answer_mapping_confidence"] = "LOW"
        q["mapping_method"] = "UNRESOLVED"
        q["mapping_confidence"] = "LOW"
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
            if len(val_clean) >= 2 and (val_clean in str(opt).strip().lower() or str(opt).strip().lower() in val_clean):
                return chr(65 + idx)
        return None

    # STAGE 1: Explicit question number matching with group awareness (Q1 -> Answer 1)
    for q in list(unmatched_questions):
        q_num = q.get("question_number")
        if q_num is None:
            continue

        q_file = q.get("source_file") or q.get("question_source_image")
        q_chap = str(q.get("source_chapter") or q.get("topic") or q.get("question_group") or "").lower().strip()

        # Find answer candidates
        candidates = []
        for idx, a in enumerate(answers):
            if idx in matched_answer_indices:
                continue
            
            a_num = a.get("question_number")
            if a_num is not None and str(a_num) == str(q_num):
                candidates.append((idx, a))

        if not candidates:
            continue

        best_match = None
        if len(candidates) == 1:
            idx, a = candidates[0]
            a_group = a.get("answer_key_group") or a.get("source_chapter") or a.get("source_section")
            if not a_group or are_groups_compatible(q_chap, a_group, q_file, a.get("source_file")):
                best_match = (idx, a, "EXPLICIT")
            else:
                best_match = None
        else:
            # Multiple candidates with same question number — filter by group compatibility
            compatible_candidates = []
            for idx, a in candidates:
                a_group = a.get("answer_key_group") or a.get("source_chapter") or a.get("source_section")
                if are_groups_compatible(q_chap, a_group, q_file, a.get("source_file")):
                    compatible_candidates.append((idx, a))
                elif q_file and a.get("source_file") and q_file == a.get("source_file"):
                    compatible_candidates.append((idx, a))

            if len(compatible_candidates) == 1:
                idx, a = compatible_candidates[0]
                best_match = (idx, a, "EXPLICIT_GROUPED")
            elif len(compatible_candidates) > 1:
                best_match = None
            else:
                best_match = None

        if best_match:
            idx, a, method = best_match
            ans_val = a.get("answer")
            options = q.get("options", [])
            opt_letter = get_option_letter_for_text(options, ans_val)
            
            q["source_answer_key"] = opt_letter or ans_val
            q["source_answer_text"] = ans_val if opt_letter else (ans_val or "")
            q["correct_answer"] = ans_val if opt_letter else (ans_val or "")
            q["source_answer_explanation"] = a.get("explanation")
            q["question_source_image"] = q_file
            q["question_group"] = q.get("question_group") or q_file
            q["answer_source_image"] = a.get("source_file")
            q["answer_key_group"] = a.get("answer_key_group") or a.get("source_chapter") or a.get("source_section")
            q["mapping_method"] = method
            q["mapping_confidence"] = "HIGH"
            q["answer_mapping_method"] = method
            q["answer_mapping_confidence"] = "HIGH"
            q["answer_mapping_score"] = 0.98 if method == "EXPLICIT" else 0.95
            q["answer_source_file"] = a.get("source_file")
            q["answer_source_page"] = a.get("source_page")
            q["answer_source_role"] = a.get("source_role", "ANSWER_SOURCE")
            
            matched_answer_indices.add(idx)
            unmatched_questions.remove(q)
        else:
            if len(candidates) > 1:
                q["source_answer_key"] = None
                q["source_answer_text"] = None
                q["question_source_image"] = q_file
                q["question_group"] = q.get("question_group") or q_file
                q["answer_mapping_method"] = "AMBIGUOUS"
                q["answer_mapping_confidence"] = "LOW"
                q["answer_mapping_score"] = 0.0
                q["mapping_method"] = "AMBIGUOUS"
                q["mapping_confidence"] = "LOW"
                q["validation_status"] = "AMBIGUOUS"
                q["review_required"] = True
                q["warnings"] = f"Multiple conflicting answers found for question #{q_num} across groups."
                unmatched_questions.remove(q)

    # STAGE 2: Sequential Matching (Only if evidence is strong: single group, counts match exactly, no duplicate numbers)
    remaining_ans = [(idx, a) for idx, a in enumerate(answers) if idx not in matched_answer_indices]
    if len(unmatched_questions) == len(remaining_ans) and len(unmatched_questions) > 0:
        q_groups = set(normalize_group_key(q.get("source_file") or q.get("question_group")) for q in unmatched_questions)
        a_groups = set(normalize_group_key(a.get("answer_key_group") or a.get("source_chapter") or a.get("source_section")) for idx, a in remaining_ans)
        
        q_nums = [q.get("question_number") for q in unmatched_questions]
        has_number_duplicates = len(set(n for n in q_nums if n is not None)) < len([n for n in q_nums if n is not None])
        
        # Only allow sequential matching when no group conflicts and no duplicate numbers exist
        if not has_number_duplicates and len(q_groups) <= 1 and len(a_groups) <= 1 and (not q_groups or not a_groups or q_groups == a_groups):
            for idx_q, q in enumerate(list(unmatched_questions)):
                idx_a, a = remaining_ans[idx_q]
                ans_val = a.get("answer")
                options = q.get("options", [])
                opt_letter = get_option_letter_for_text(options, ans_val)
                
                q_file = q.get("source_file") or q.get("question_source_image")
                q["source_answer_key"] = opt_letter or ans_val
                q["source_answer_text"] = ans_val if opt_letter else (ans_val or "")
                q["correct_answer"] = ans_val if opt_letter else (ans_val or "")
                q["source_answer_explanation"] = a.get("explanation")
                q["question_source_image"] = q_file
                q["question_group"] = q.get("question_group") or q_file
                q["answer_source_image"] = a.get("source_file")
                q["answer_key_group"] = a.get("answer_key_group") or a.get("source_chapter") or a.get("source_section")
                q["mapping_method"] = "SEQUENTIAL"
                q["mapping_confidence"] = "MEDIUM"
                q["answer_mapping_method"] = "SEQUENTIAL"
                q["answer_mapping_confidence"] = "MEDIUM"
                q["answer_mapping_score"] = 0.84
                q["answer_source_file"] = a.get("source_file")
                q["answer_source_page"] = a.get("source_page")
                q["answer_source_role"] = a.get("source_role", "ANSWER_SOURCE")
                
                matched_answer_indices.add(idx_a)
                unmatched_questions.remove(q)

    # STAGE 3: Semantic Option Matching (Answer matches one option text within compatible group)
    for q in list(unmatched_questions):
        options = q.get("options", [])
        if not options:
            continue
            
        q_file = q.get("source_file") or q.get("question_source_image")
        q_chap = str(q.get("source_chapter") or q.get("topic") or q.get("question_group") or "").lower().strip()

        semantic_matches = []
        for idx, a in enumerate(answers):
            if idx in matched_answer_indices:
                continue
                
            ans_val = str(a.get("answer", "")).strip()
            opt_letter = get_option_letter_for_text(options, ans_val)
            if opt_letter:
                a_group = a.get("answer_key_group") or a.get("source_chapter") or a.get("source_section")
                if not a_group or are_groups_compatible(q_chap, a_group, q_file, a.get("source_file")):
                    semantic_matches.append((idx, a, opt_letter))

        if len(semantic_matches) == 1:
            idx_a, a, opt_letter = semantic_matches[0]
            ans_val = a.get("answer")
            q["source_answer_key"] = opt_letter
            q["source_answer_text"] = ans_val
            q["correct_answer"] = ans_val
            q["source_answer_explanation"] = a.get("explanation")
            q["question_source_image"] = q_file
            q["question_group"] = q.get("question_group") or q_file
            q["answer_source_image"] = a.get("source_file")
            q["answer_key_group"] = a.get("answer_key_group") or a.get("source_chapter") or a.get("source_section")
            q["mapping_method"] = "SEMANTIC"
            q["mapping_confidence"] = "LOW"
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
                    idx_a = next((i for i, ans in enumerate(answers) if ans == a), None)
                    if idx_a is not None and idx_a not in matched_answer_indices:
                        ans_val = a.get("answer")
                        options = q.get("options", [])
                        opt_letter = get_option_letter_for_text(options, ans_val)
                        
                        q_file = q.get("source_file") or q.get("question_source_image")
                        q["source_answer_key"] = opt_letter or ans_val
                        q["source_answer_text"] = ans_val if opt_letter else (ans_val or "")
                        q["correct_answer"] = ans_val if opt_letter else (ans_val or "")
                        q["source_answer_explanation"] = a.get("explanation")
                        q["question_source_image"] = q_file
                        q["question_group"] = q.get("question_group") or q_file
                        q["answer_source_image"] = a.get("source_file")
                        q["answer_key_group"] = a.get("answer_key_group") or a.get("source_chapter") or a.get("source_section")
                        q["mapping_method"] = "AI_FALLBACK"
                        q["mapping_confidence"] = "LOW"
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
        q_file = q.get("source_file") or q.get("question_source_image")
        q["question_source_image"] = q_file
        q["question_group"] = q.get("question_group") or q_file
        
        inline_ans = q.get("correct_answer")
        if inline_ans and str(inline_ans).strip() and not q.get("source_answer_key"):
            options = q.get("options", [])
            opt_letter = get_option_letter_for_text(options, inline_ans)
            q["source_answer_key"] = opt_letter or inline_ans
            q["source_answer_text"] = inline_ans if opt_letter else (inline_ans or "")
            q["mapping_method"] = "INLINE"
            q["mapping_confidence"] = "HIGH"
            q["answer_mapping_method"] = "INLINE"
            q["answer_mapping_confidence"] = "HIGH"
            q["answer_mapping_score"] = 0.95
        elif not q.get("source_answer_key"):
            q["source_answer_key"] = None
            q["source_answer_text"] = None
            q["mapping_method"] = "UNRESOLVED"
            q["mapping_confidence"] = "LOW"
            q["answer_mapping_method"] = "UNRESOLVED"
            q["answer_mapping_confidence"] = "LOW"
            q["answer_mapping_score"] = 0.0
            q["validation_status"] = "REVIEW_REQUIRED"
            q["review_required"] = True
            q["warnings"] = "Answer could not be reliably matched."

    # Final Option Check: Duplicate Option Values Detection
    for q in questions:
        options = q.get("options", [])
        if options and len(options) >= 2:
            unique_opts = set(str(o).strip().lower() for o in options if o is not None)
            if len(unique_opts) < len(options):
                q["validation_status"] = "AMBIGUOUS"
                q["review_required"] = True
                q["warnings"] = "Duplicate MCQ option values detected."

    # Default final_answers
    for q in questions:
        q["final_answer_key"] = q["source_answer_key"]
        q["final_answer_text"] = q["source_answer_text"]

    return questions
