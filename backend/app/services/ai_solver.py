import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from app.config import settings
from app.services.azure_openai import get_client, get_critic_client, _call_azure_with_retry

INDEPENDENT_SOLVER_SYSTEM_PROMPT = """You are an expert assessment solver and subject matter validator.
Your task is to independently solve the given multiple-choice question and determine the single most correct answer based ONLY on the provided question stem and options.

STRICT RULES:
1. You are NOT provided with any source or expected answer. Solve the question completely independently.
2. Carefully evaluate each option (A, B, C, D) and explain why the selected option is correct and why others are incorrect.
3. Be rigorous, scientifically exact, and mathematically precise.
4. If the question is ambiguous, has multiple correct options, has NO correct options, or lacks necessary information (e.g. missing values, corrupted text, missing diagram references), indicate that clearly.
5. Provide a concise, clear reasoning summary (1-2 sentences) suitable for an educator.
6. Return ONLY a valid JSON object matching the requested schema.
"""

BLIND_CRITIC_SYSTEM_PROMPT = """You are an independent peer review assessment solver and subject matter specialist.
Your task is to independently solve the given multiple-choice question from first principles without seeing any prior solver's work.

STRICT RULES:
1. You are NOT provided with any prior solver answer or candidate reasoning. Solve the question completely independently.
2. Carefully analyze each option (A, B, C, D) and verify the mathematically and scientifically sound choice.
3. Watch out for subtle traps, distractors, ambiguous phrasing, or unit conversion pitfalls.
4. Provide a concise, clear verification reasoning summary.
5. Return ONLY a valid JSON object matching the requested schema.
"""

CRITIC_VERIFIER_SYSTEM_PROMPT = """You are an expert assessment peer reviewer and critic.
Your role is to rigorously check a proposed answer and reasoning for a multiple-choice question.
Verify if the candidate answer is truly correct, if the mathematical/logical/scientific reasoning is sound, or if there are subtle flaws, traps, or alternative interpretations.
Return ONLY a valid JSON object matching the requested schema.
"""

AMBIGUITY_CHECK_SYSTEM_PROMPT = """You are an assessment quality auditor.
Your job is to inspect question stems and options for defects:
- Missing critical data, formulas, or numbers (e.g., OCR dropped characters)
- Unclear or ambiguous phrasing where more than one option could be considered correct
- Missing visual/diagram/table dependencies
- Malformed, duplicate, or nonsensical options
Return ONLY a valid JSON object matching the requested schema.
"""

def solve_question_independently(
    question_stem: str,
    options: list[str],
    subject: str = "General",
    context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Independently solves an MCQ question WITHOUT any knowledge of source answers.
    Prevents confirmation bias.
    """
    client = get_client()
    ctx = context or {}
    
    formatted_options = "\n".join([
        f"{chr(65 + i)}) {opt}" for i, opt in enumerate(options)
    ]) if options else "No options provided."

    prompt = f"""Subject: {subject}
Grade/Class: {ctx.get('gradeClass', 'General')}
Topic: {ctx.get('chapterTopic', 'General')}

QUESTION:
{question_stem}

OPTIONS:
{formatted_options}

Determine the correct option letter (e.g., "A", "B", "C", "D") and the exact text of the correct option.
If no options are correct or question cannot be solved, state that clearly.

Return JSON in this format:
{{
  "selected_option_letter": "A",
  "selected_option_text": "...",
  "reasoning_summary": "Concise 1-2 sentence explanation of why this answer is scientifically/mathematically correct.",
  "is_solvable": true,
  "confidence_rating": "HIGH",
  "detected_defects": []
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
                    {"role": "system", "content": INDEPENDENT_SOLVER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            }
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return payload
    except Exception as e:
        return {
            "selected_option_letter": None,
            "selected_option_text": None,
            "reasoning_summary": f"AI Solver error: {str(e)}",
            "is_solvable": False,
            "confidence_rating": "UNCERTAIN",
            "detected_defects": ["API_CALL_FAILED"]
        }

def solve_question_blind_second_pass(
    question_stem: str,
    options: list[str],
    subject: str = "General",
    context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Second independent solver pass (Blind Critic).
    Uses a distinct system prompt and configurable critic model deployment
    WITHOUT seeing the first solver's candidate answer or reasoning.
    """
    client, deployment_name = get_critic_client()
    ctx = context or {}
    
    formatted_options = "\n".join([
        f"{chr(65 + i)}) {opt}" for i, opt in enumerate(options)
    ]) if options else "No options provided."

    prompt = f"""Subject: {subject}
Grade/Class: {ctx.get('gradeClass', 'General')}
Topic: {ctx.get('chapterTopic', 'General')}

QUESTION:
{question_stem}

OPTIONS:
{formatted_options}

Determine the correct option letter (e.g., "A", "B", "C", "D") and the exact text of the correct option.
If no options are correct or question cannot be solved, state that clearly.

Return JSON in this format:
{{
  "selected_option_letter": "A",
  "selected_option_text": "...",
  "reasoning_summary": "Concise 1-2 sentence explanation of why this answer is scientifically/mathematically correct.",
  "is_solvable": true,
  "confidence_rating": "HIGH",
  "detected_defects": []
}}
"""
    try:
        response = _call_azure_with_retry(
            client,
            {
                "model": deployment_name,
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": BLIND_CRITIC_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            }
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return payload
    except Exception as e:
        return {
            "selected_option_letter": None,
            "selected_option_text": None,
            "reasoning_summary": f"Blind Critic pass error: {str(e)}",
            "is_solvable": False,
            "confidence_rating": "UNCERTAIN",
            "detected_defects": ["CRITIC_API_CALL_FAILED"]
        }

# DEPRECATED: Retained for backward compatibility. The validation pipeline now uses solve_question_blind_second_pass().
def verify_with_critic(
    question_stem: str,
    options: list[str],
    candidate_letter: str | None,
    candidate_text: str | None,
    candidate_reasoning: str | None,
    subject: str = "General"
) -> dict[str, Any]:
    """
    Second-pass AI critic that checks candidate solver answer for hallucinations or subtle traps.
    Deprecated in favor of solve_question_blind_second_pass().
    """
    client = get_client()
    
    formatted_options = "\n".join([
        f"{chr(65 + i)}) {opt}" for i, opt in enumerate(options)
    ]) if options else "No options provided."

    prompt = f"""Subject: {subject}

QUESTION:
{question_stem}

OPTIONS:
{formatted_options}

PROPOSED SOLUTION TO CRITIQUE:
Option: {candidate_letter} ({candidate_text})
Reasoning: {candidate_reasoning}

Evaluate if this proposed solution is 100% correct and whether any other option could be valid.

Return JSON in this format:
{{
  "agrees_with_solver": true,
  "critic_selected_letter": "A",
  "critic_selected_text": "...",
  "critique_summary": "Concise critique and sanity check confirmation",
  "is_sound": true,
  "alternative_interpretation": null
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
                    {"role": "system", "content": CRITIC_VERIFIER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            }
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return payload
    except Exception as e:
        return {
            "agrees_with_solver": False,
            "critic_selected_letter": None,
            "critic_selected_text": None,
            "critique_summary": f"Critic check error: {str(e)}",
            "is_sound": False,
            "alternative_interpretation": "Verification failed due to connection/system issue"
        }

def solve_question_with_self_consistency(
    question_stem: str,
    options: list[str],
    subject: str = "General",
    context: dict[str, Any] | None = None,
    n_samples: int = 3,
    temperature: float = 0.4
) -> dict[str, Any]:
    """
    Performs self-consistency majority voting by running n_samples parallel solving passes.
    Used as an automated tie-breaker when primary solver and blind critic disagree.
    """
    client = get_client()
    ctx = context or {}

    formatted_options = "\n".join([
        f"{chr(65 + i)}) {opt}" for i, opt in enumerate(options)
    ]) if options else "No options provided."

    prompt = f"""Subject: {subject}
Grade/Class: {ctx.get('gradeClass', 'General')}
Topic: {ctx.get('chapterTopic', 'General')}

QUESTION:
{question_stem}

OPTIONS:
{formatted_options}

Determine the correct option letter (e.g., "A", "B", "C", "D") and the exact text of the correct option.
If no options are correct or question cannot be solved, state that clearly.

Return JSON in this format:
{{
  "selected_option_letter": "A",
  "selected_option_text": "...",
  "reasoning_summary": "Concise 1-2 sentence explanation of why this answer is scientifically/mathematically correct.",
  "is_solvable": true
}}
"""

    def run_single_sample(sample_idx: int) -> dict[str, Any]:
        try:
            response = _call_azure_with_retry(
                client,
                {
                    "model": settings.azure_openai_deployment_name,
                    "temperature": temperature,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": INDEPENDENT_SOLVER_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ]
                }
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception as e:
            return {"selected_option_letter": None, "selected_option_text": None, "reasoning_summary": str(e), "is_solvable": False}

    max_workers = min(n_samples, max(1, settings.max_ai_concurrency))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        sample_results = list(executor.map(run_single_sample, range(n_samples)))

    # Collect letter votes
    letter_votes = []
    text_by_letter = {}
    reasoning_by_letter = {}

    for res in sample_results:
        let = res.get("selected_option_letter")
        if let and isinstance(let, str):
            clean_let = let.strip().upper()
            letter_votes.append(clean_let)
            if clean_let not in text_by_letter and res.get("selected_option_text"):
                text_by_letter[clean_let] = res.get("selected_option_text")
            if clean_let not in reasoning_by_letter and res.get("reasoning_summary"):
                reasoning_by_letter[clean_let] = res.get("reasoning_summary")

    if not letter_votes:
        return {
            "selected_option_letter": None,
            "selected_option_text": None,
            "reasoning_summary": "Self-consistency voting failed to produce valid sample answers.",
            "vote_agreement_ratio": 0.0,
            "votes": {},
            "is_solvable": False
        }

    counts = Counter(letter_votes)
    majority_letter, top_count = counts.most_common(1)[0]
    agreement_ratio = round(top_count / len(letter_votes), 2)

    return {
        "selected_option_letter": majority_letter,
        "selected_option_text": text_by_letter.get(majority_letter, ""),
        "reasoning_summary": reasoning_by_letter.get(majority_letter, f"Majority vote ({top_count}/{len(letter_votes)}) resolution."),
        "vote_agreement_ratio": agreement_ratio,
        "votes": dict(counts),
        "is_solvable": True,
        "n_samples": n_samples
    }

def detect_ambiguity_via_ai(
    question_stem: str,
    options: list[str]
) -> dict[str, Any]:
    """
    Calls Azure OpenAI with AMBIGUITY_CHECK_SYSTEM_PROMPT to detect subtle semantic ambiguities
    or missing contextual dependencies in complex/long questions.
    """
    client = get_client()
    formatted_options = "\n".join([
        f"{chr(65 + i)}) {opt}" for i, opt in enumerate(options)
    ]) if options else "No options provided."

    prompt = f"""QUESTION TO AUDIT:
{question_stem}

OPTIONS:
{formatted_options}

Evaluate whether this question has flaws, missing information, visual dependencies, or multiple interpretations.

Return JSON in this format:
{{
  "is_ambiguous": true,
  "defects": ["AMBIGUOUS_PHRASING" | "MISSING_INFORMATION" | "VISUAL_DEPENDENCY_DETECTED"],
  "ambiguity_reason": "Specific defect explanation if any, or null"
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
                    {"role": "system", "content": AMBIGUITY_CHECK_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            }
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return payload
    except Exception:
        return {"is_ambiguous": False, "defects": [], "ambiguity_reason": None}

def detect_question_ambiguity_and_defects(
    question_stem: str,
    options: list[str]
) -> dict[str, Any]:
    """
    Evaluates question stem and options for structural defects, missing info, OCR artifacts, and ambiguity.
    Uses fast deterministic rules first; falls back to AI ambiguity prompt for long/complex stems.
    """
    # Fast deterministic checks first
    defects = []
    
    if not question_stem or len(question_stem.strip()) < 5:
        defects.append("STEM_TOO_SHORT_OR_EMPTY")

    # Incomplete stems e.g., ending with unfinished symbol or equation "=" without right side or missing question mark
    stripped = question_stem.strip() if question_stem else ""
    if stripped.endswith("=") or stripped.endswith("+") or stripped.endswith("-") or stripped.endswith("*") or stripped.endswith("/"):
        defects.append("INCOMPLETE_EQUATION_OR_PROMPT")

    if not options or len(options) < 2:
        defects.append("INSUFFICIENT_OPTIONS")

    # Duplicate options check
    cleaned_options = [opt.strip().lower() for opt in options if opt and opt.strip()]
    if len(cleaned_options) != len(set(cleaned_options)) and len(cleaned_options) > 1:
        defects.append("DUPLICATE_OPTIONS")

    # Visual dependencies check in text
    visual_keywords = [
        "shown in the figure", "given in the diagram", "refer to the image",
        "shown in the graph", "in the table below", "as illustrated",
        "refer to diagram", "shown below:"
    ]
    has_visual_keyword = any(kw in stripped.lower() for kw in visual_keywords)
    if has_visual_keyword:
        defects.append("VISUAL_DEPENDENCY_DETECTED")

    # Check for missing blanks or OCR markers like "[?]" or "?" inside expression
    if "[?]" in stripped or ("when x =" in stripped.lower() and not re_has_val(stripped)):
        defects.append("MISSING_INFORMATION")

    # If already severely defective, return early without AI call
    if "STEM_TOO_SHORT_OR_EMPTY" in defects or "INSUFFICIENT_OPTIONS" in defects:
        return {
            "is_ambiguous": True,
            "has_defects": True,
            "defects": defects,
            "ambiguity_reason": "Question is incomplete or options are missing."
        }

    # Second-tier check: if fast heuristics found no defects but the question is long (> 40 words), run AI ambiguity check
    if not defects and len(stripped.split()) > 40:
        ai_ambiguity = detect_ambiguity_via_ai(stripped, options)
        if ai_ambiguity.get("is_ambiguous") or ai_ambiguity.get("defects"):
            ai_defects = ai_ambiguity.get("defects", [])
            defects.extend(ai_defects)
            return {
                "is_ambiguous": bool(ai_ambiguity.get("is_ambiguous")),
                "has_defects": len(defects) > 0,
                "defects": defects,
                "ambiguity_reason": ai_ambiguity.get("ambiguity_reason")
            }

    return {
        "is_ambiguous": "DUPLICATE_OPTIONS" in defects or "INCOMPLETE_EQUATION_OR_PROMPT" in defects or "MISSING_INFORMATION" in defects,
        "has_defects": len(defects) > 0,
        "defects": defects,
        "ambiguity_reason": "Visual context or structural defect detected" if defects else None
    }

def re_has_val(text: str) -> bool:
    import re
    return bool(re.search(r"x\s*=\s*[-+]?\d+", text, re.IGNORECASE))
