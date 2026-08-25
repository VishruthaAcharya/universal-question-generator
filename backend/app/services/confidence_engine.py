from typing import Any

def calculate_evidence_based_confidence(
    solver_agrees: bool,
    critic_agrees: bool,
    deterministic_result: dict[str, Any],
    extraction_confidence: float = 0.95,
    option_count: int = 4,
    has_duplicate_options: bool = False,
    is_ambiguous: bool = False,
    has_visual_dependency: bool = False,
    has_missing_info: bool = False,
    is_solvable: bool = True,
    solver_answer: str | None = None,
    source_answer: str | None = None,
    vote_agreement_ratio: float | None = None,
) -> tuple[float, str]:
    """
    Synthesizes an evidence-based confidence score (0.00 - 1.00) from distinct signals.
    Does NOT use self-reported LLM confidence.
    Optionally factors in vote_agreement_ratio from self-consistency voting when tie-breaking was required.
    
    Returns:
        (confidence_score, confidence_level)
    """
    if not is_solvable or not solver_answer:
        return 0.30, "UNCERTAIN"

    if has_missing_info:
        return 0.45, "UNCERTAIN"

    if has_visual_dependency:
        return 0.50, "UNCERTAIN"

    # Base score component weights
    # 1. Base solver soundness
    score = 0.50

    # 2. Deterministic validation bonus or penalty
    if deterministic_result.get("verified"):
        det_letter = deterministic_result.get("selected_option_letter")
        if det_letter == solver_answer:
            score += 0.30  # Strong proof
        else:
            score -= 0.35  # Deterministic contradiction!
    else:
        # Conceptual questions without deterministic calculation receive standard baseline
        score += 0.15

    # 3. Critic agreement bonus or penalty
    if critic_agrees:
        score += 0.15
    else:
        score -= 0.25  # Independent blind passes disagreed

    # 3b. Self-consistency majority vote agreement (if tie-breaking was triggered)
    if vote_agreement_ratio is not None:
        if vote_agreement_ratio >= 0.8:
            score += 0.10  # Strong consensus among multiple samples
        elif vote_agreement_ratio <= 0.5:
            score -= 0.15  # Weak / split consensus

    # 4. Extraction & Option quality weight
    ext_factor = max(0.0, min(1.0, extraction_confidence))
    score += (ext_factor - 0.5) * 0.10  # adjust +/- 0.05 based on OCR/extraction

    if option_count >= 4 and not has_duplicate_options:
        score += 0.05
    elif has_duplicate_options or option_count < 2:
        score -= 0.30

    # 5. Penalties
    if is_ambiguous:
        score -= 0.35

    # Clamp score to [0.05, 0.99]
    final_score = round(max(0.05, min(0.99, score)), 2)

    # Determine confidence level
    if final_score >= 0.95:
        level = "HIGH"
    elif final_score >= 0.85:
        level = "MEDIUM"
    elif final_score >= 0.70:
        level = "LOW"
    else:
        level = "UNCERTAIN"

    return final_score, level
