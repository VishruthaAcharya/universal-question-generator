import hashlib
import json
import time
import os
from pathlib import Path
from typing import Any
from app.config import settings
from app.services.ai_solver import (
    solve_question_independently,
    solve_question_blind_second_pass,
    solve_question_with_self_consistency,
    verify_with_critic,
    detect_question_ambiguity_and_defects
)
from app.services.deterministic_validator import run_deterministic_validator
from app.services.confidence_engine import calculate_evidence_based_confidence

CACHE_VERSION = "v3_validation"
CACHE_DIR = Path("storage/cache/validation")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# In-memory validation cache
_VALIDATION_MEMORY_CACHE: dict[str, dict[str, Any]] = {}

def compute_question_validation_hash(
    question_stem: str,
    options: list[str],
    subject: str = "General",
    context: dict[str, Any] | None = None
) -> str:
    """Computes a unique SHA-256 fingerprint for a question and its options."""
    payload = {
        "stem": question_stem.strip().lower(),
        "options": [opt.strip().lower() for opt in options],
        "subject": (subject or "General").strip().lower(),
        "context": context or {}
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

def get_cached_validation(q_hash: str) -> dict[str, Any] | None:
    """Returns cached validation result if existing and version matches."""
    if q_hash in _VALIDATION_MEMORY_CACHE:
        entry = _VALIDATION_MEMORY_CACHE[q_hash]
        if entry.get("version") == CACHE_VERSION:
            return entry.get("result")

    cache_file = CACHE_DIR / f"{q_hash}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if data.get("version") == CACHE_VERSION:
                res = data.get("result")
                _VALIDATION_MEMORY_CACHE[q_hash] = data
                return res
        except Exception:
            cache_file.unlink(missing_ok=True)
    return None

def save_cached_validation(q_hash: str, result: dict[str, Any]):
    """Persists validation result to cache."""
    entry = {
        "version": CACHE_VERSION,
        "hash": q_hash,
        "result": result
    }
    _VALIDATION_MEMORY_CACHE[q_hash] = entry
    cache_file = CACHE_DIR / f"{q_hash}.json"
    try:
        cache_file.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Validation cache write warning: {e}")

def normalize_answer_key(raw_ans: str | None, options: list[str]) -> tuple[str | None, str | None]:
    """
    Normalizes an answer key (e.g. 'A', '1', 'Newton', 'Option B') to (letter, option_text).
    """
    if not raw_ans or not str(raw_ans).strip():
        return None, None
        
    s = str(raw_ans).strip()
    s_upper = s.upper()

    # If it's a letter A, B, C, D
    label_map = {"A": 0, "B": 1, "C": 2, "D": 3, "1": 0, "2": 1, "3": 2, "4": 3, "OPTION A": 0, "OPTION B": 1, "OPTION C": 2, "OPTION D": 3}
    if s_upper in label_map:
        idx = label_map[s_upper]
        if idx < len(options):
            return chr(65 + idx), options[idx].strip()
        return chr(65 + idx), None

    # Match text to options directly
    for i, opt in enumerate(options):
        if s.lower() == opt.strip().lower():
            return chr(65 + i), opt.strip()

    # Substring match
    for i, opt in enumerate(options):
        if s.lower() in opt.strip().lower():
            return chr(65 + i), opt.strip()

    return None, s

def validate_single_question_answer(
    question_data: dict[str, Any],
    subject: str = "General",
    context: dict[str, Any] | None = None,
    use_cache: bool = True
) -> dict[str, Any]:
    """
    Executes the multi-stage, independent AI + deterministic answer validation pipeline.
    """
    ctx = context or {}
    q_id = str(question_data.get("id") or question_data.get("question_id") or "q_unknown")
    row_number = question_data.get("row_number") or 1

    # Extract stem and options
    stem = ""
    for k in ["Question", "question", "item_text", "prompt", "stem"]:
        if k in question_data and question_data[k]:
            stem = str(question_data[k]).strip()
            break

    options = []
    # Try options array first
    if "options" in question_data and isinstance(question_data["options"], list) and question_data["options"]:
        options = [str(o).strip() for o in question_data["options"] if str(o).strip()]
    else:
        # Check standard option keys
        for opt_key in ["Option A", "Option B", "Option C", "Option D", "option_1", "option_2", "option_3", "option_4", "Answer 1", "Answer 2", "Answer 3", "Answer 4"]:
            if opt_key in question_data and question_data[opt_key]:
                val = str(question_data[opt_key]).strip()
                if val:
                    options.append(val)

    # Extract source answer
    raw_source_answer = None
    for ans_key in ["Correct Answer", "correct_answer", "Answer", "answer", "source_answer", "Key"]:
        if ans_key in question_data and question_data[ans_key]:
            raw_source_answer = str(question_data[ans_key]).strip()
            break

    source_letter, source_text = normalize_answer_key(raw_source_answer, options)

    # Extract metadata confidence if available
    metadata_fields = question_data.get("source_metadata", {}).get("fields", {}) if isinstance(question_data.get("source_metadata"), dict) else {}
    extraction_conf = 0.95
    if metadata_fields:
        confs = [f.get("confidence", 0.95) for f in metadata_fields.values() if isinstance(f, dict) and "confidence" in f]
        if confs:
            extraction_conf = sum(confs) / len(confs)

    # 1. Check Cache
    q_hash = compute_question_validation_hash(stem, options, subject, ctx)
    if use_cache:
        cached_result = get_cached_validation(q_hash)
        if cached_result:
            # Update dynamic runtime fields (source_answer parity)
            res = dict(cached_result)
            res["question_id"] = q_id
            res["row_number"] = row_number
            res["source_answer"] = source_letter or raw_source_answer
            res["source_answer_text"] = source_text

            # Re-evaluate parity against this specific question's source answer
            ai_ans = res.get("ai_answer")
            if source_letter and ai_ans:
                match = (source_letter.upper() == ai_ans.upper())
                res["answer_match"] = match
                if not match:
                    res["validation_status"] = "ANSWER_CONFLICT"
                    res["review_required"] = True
                    res["review_priority"] = 1
                else:
                    res["answer_match"] = True
            return res

    # 2. Defect & Quality Check
    quality_audit = detect_question_ambiguity_and_defects(stem, options)
    has_defects = quality_audit.get("has_defects", False)
    defects = quality_audit.get("defects", [])
    is_ambiguous = quality_audit.get("is_ambiguous", False)
    has_visual = "VISUAL_DEPENDENCY_DETECTED" in defects
    has_missing_info = "MISSING_INFORMATION" in defects or "INCOMPLETE_EQUATION_OR_PROMPT" in defects

    validation_methods = []

    # 3. Deterministic Validation Pass
    deterministic_res = run_deterministic_validator(stem, options, subject)
    if deterministic_res.get("verified"):
        validation_methods.append(deterministic_res.get("method", "DETERMINISTIC_VALIDATION"))

    # 4. Independent AI Solver Pass (Zero knowledge of source answer)
    ai_solver_res = solve_question_independently(stem, options, subject, ctx)
    validation_methods.append("INDEPENDENT_AI_SOLVER")

    solver_letter = ai_solver_res.get("selected_option_letter")
    solver_text = ai_solver_res.get("selected_option_text")
    solver_reasoning = ai_solver_res.get("reasoning_summary")
    is_solvable = ai_solver_res.get("is_solvable", True)

    # 5. Blind Critic Second-Pass (Zero candidate answer knowledge)
    blind_critic_res = solve_question_blind_second_pass(stem, options, subject, ctx)
    blind_letter = blind_critic_res.get("selected_option_letter")
    blind_text = blind_critic_res.get("selected_option_text")
    blind_reasoning = blind_critic_res.get("reasoning_summary")

    # Programmatic comparison between two independent passes
    critic_agreed = bool(solver_letter and blind_letter and str(solver_letter).strip().upper() == str(blind_letter).strip().upper())
    if critic_agreed:
        validation_methods.append("AI_BLIND_CRITIC_AGREED")

    # 6. Candidate Resolution & Self-Consistency Tie-Breaking
    final_ai_letter = solver_letter
    final_ai_text = solver_text
    final_reasoning = solver_reasoning or "Validated by AI solver."
    vote_agreement_ratio: float | None = None

    # Deterministic validation takes first priority if verified
    if deterministic_res.get("verified"):
        det_letter = deterministic_res.get("selected_option_letter")
        det_text = deterministic_res.get("selected_option_text")
        if det_letter:
            final_ai_letter = det_letter
            final_ai_text = det_text
            final_reasoning = deterministic_res.get("reasoning") or final_reasoning
    elif not critic_agreed and solver_letter and blind_letter:
        # Disagreement between independent solver and blind critic -> Trigger self-consistency voting tie-breaker
        self_consistency_res = solve_question_with_self_consistency(
            question_stem=stem,
            options=options,
            subject=subject,
            context=ctx,
            n_samples=3,
            temperature=0.4
        )
        vote_agreement_ratio = self_consistency_res.get("vote_agreement_ratio")
        majority_letter = self_consistency_res.get("selected_option_letter")
        if majority_letter:
            final_ai_letter = majority_letter
            final_ai_text = self_consistency_res.get("selected_option_text") or final_ai_text
            final_reasoning = self_consistency_res.get("reasoning_summary") or f"Resolved via majority vote ({vote_agreement_ratio*100:.0f}% agreement)."
            validation_methods.append("SELF_CONSISTENCY_MAJORITY_VOTE")

    # 7. Evidence-Based Confidence Calculation
    confidence_score, confidence_level = calculate_evidence_based_confidence(
        solver_agrees=bool(solver_letter and is_solvable),
        critic_agrees=critic_agreed,
        deterministic_result=deterministic_res,
        extraction_confidence=extraction_conf,
        option_count=len(options),
        has_duplicate_options="DUPLICATE_OPTIONS" in defects,
        is_ambiguous=is_ambiguous,
        has_visual_dependency=has_visual,
        has_missing_info=has_missing_info,
        is_solvable=is_solvable,
        solver_answer=final_ai_letter,
        source_answer=source_letter,
        vote_agreement_ratio=vote_agreement_ratio
    )

    # 8. Status & Review Priority Classification
    validation_status = "AI_VALIDATED"
    review_required = False
    review_priority = 5

    # Check for visual dependency
    if has_visual:
        validation_status = "VISUAL_CONTEXT_REQUIRED"
        review_required = True
        review_priority = 4
        final_reasoning = "Visual context, diagram, or chart required to solve reliably."
    elif has_missing_info:
        validation_status = "MISSING_INFORMATION"
        review_required = True
        review_priority = 4
        final_reasoning = "Question text is incomplete or critical variables/symbols were omitted."
    elif is_ambiguous or "DUPLICATE_OPTIONS" in defects:
        validation_status = "AMBIGUOUS"
        review_required = True
        review_priority = 3
        final_reasoning = "Question is ambiguous or contains duplicate/overlapping options."
    elif not is_solvable or not final_ai_letter:
        validation_status = "UNCERTAIN"
        review_required = True
        review_priority = 2
        final_reasoning = "AI could not determine a definitive answer with high reliability."
    elif confidence_level == "UNCERTAIN" or confidence_score < 0.70:
        validation_status = "UNCERTAIN"
        review_required = True
        review_priority = 2

    # 9. Source Answer Parity Check
    answer_match = True
    if source_letter and final_ai_letter:
        if source_letter.upper() != final_ai_letter.upper():
            answer_match = False
            validation_status = "ANSWER_CONFLICT"
            review_required = True
            review_priority = 1
            final_reasoning = f"Source answer ({source_letter}) conflicts with AI verified answer ({final_ai_letter})."
        else:
            answer_match = True
    elif not source_letter:
        # No source answer provided
        answer_match = None

    signals_payload = {
        "solver_agreed": bool(solver_letter),
        "critic_agreed": critic_agreed,
        "deterministic_verified": deterministic_res.get("verified", False),
        "extraction_confidence": round(extraction_conf, 2),
        "option_count": len(options),
        "defects_detected": defects,
        "vote_agreement_ratio": vote_agreement_ratio
    }

    result = {
        "question_id": q_id,
        "row_number": row_number,
        "ai_answer": final_ai_letter,
        "ai_answer_text": final_ai_text,
        "source_answer": source_letter or raw_source_answer,
        "source_answer_text": source_text,
        "answer_match": answer_match,
        "confidence": confidence_score,
        "confidence_level": confidence_level,
        "validation_status": validation_status,
        "validation_methods": validation_methods,
        "review_required": review_required,
        "review_priority": review_priority,
        "reason": final_reasoning,
        "subject": deterministic_res.get("subject", subject),
        "signals": signals_payload
    }

    # 10. Calibration Logging Hook
    import os
    if settings.confidence_calibration_log or os.getenv("CONFIDENCE_CALIBRATION_LOG", "").lower() in ("true", "1"):
        try:
            calib_dir = Path("storage")
            calib_dir.mkdir(parents=True, exist_ok=True)
            calib_file = calib_dir / "calibration_log.jsonl"
            log_row = {
                "question_id": q_id,
                "signals": signals_payload,
                "confidence_score": confidence_score,
                "confidence_level": confidence_level,
                "validation_status": validation_status,
                "timestamp": time.time()
            }
            with open(calib_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_row) + "\n")
        except Exception as e:
            print(f"Calibration log write warning: {e}")

    # Save to Cache
    save_cached_validation(q_hash, result)
    return result

def validate_questions_batch_answers(
    questions: list[dict[str, Any]],
    subject: str = "General",
    context: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Validates a batch of questions sequentially or concurrently.
    """
    results = []
    for q in questions:
        res = validate_single_question_answer(q, subject=subject, context=context)
        results.append(res)
    return results
