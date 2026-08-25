import pytest
import json
from pathlib import Path
from unittest.mock import patch
from app.services.deterministic_validator import (
    deterministic_math_solve,
    deterministic_physics_solve,
    deterministic_chemistry_solve,
    deterministic_biology_solve,
    deterministic_unit_conversion_solve,
    run_deterministic_validator,
    detect_subject
)
from app.services.confidence_engine import calculate_evidence_based_confidence
from app.services.ai_solver import (
    detect_question_ambiguity_and_defects,
    solve_question_independently,
    solve_question_blind_second_pass,
    solve_question_with_self_consistency
)
from app.services.answer_validation_engine import (
    validate_single_question_answer,
    validate_questions_batch_answers,
    compute_question_validation_hash,
    get_cached_validation,
    save_cached_validation,
    CACHE_VERSION
)

# 1. Test Deterministic Math Solver (Arithmetic, Substitution, Ratio)
def test_math_deterministic_calculation():
    stem = "What is the value of 2x + 3 when x = 5?"
    options = ["10", "13", "15", "8"]
    res = deterministic_math_solve(stem, options)
    assert res["verified"] is True
    assert res["selected_option_letter"] == "B"
    assert res["selected_option_text"] == "13"

def test_math_percentage_calculation():
    stem = "What is 20% of 150?"
    options = ["25", "30", "35", "40"]
    res = deterministic_math_solve(stem, options)
    assert res["verified"] is True
    assert res["selected_option_letter"] == "B"
    assert res["selected_option_text"] == "30"

def test_deterministic_ratio_proportions():
    stem = "If a:b = 3:5 and a = 12, find b."
    options = ["15", "18", "20", "25"]
    res = deterministic_math_solve(stem, options)
    assert res["verified"] is True
    assert res["selected_option_letter"] == "C"
    assert res["selected_option_text"] == "20"

# 2. Test Deterministic Unit Conversion Solver
def test_deterministic_unit_conversion_km_to_m():
    stem = "Convert 5 km to meters."
    options = ["500 m", "5000 m", "50 m", "50000 m"]
    res = deterministic_unit_conversion_solve(stem, options)
    assert res["verified"] is True
    assert res["selected_option_letter"] == "B"
    assert res["selected_option_text"] == "5000 m"

def test_deterministic_unit_conversion_kg_to_g():
    stem = "Convert 4 kg to grams."
    options = ["400 g", "4000 g", "40 g", "0.004 g"]
    res = deterministic_unit_conversion_solve(stem, options)
    assert res["verified"] is True
    assert res["selected_option_letter"] == "B"
    assert res["selected_option_text"] == "4000 g"

def test_deterministic_unit_conversion_hours_to_sec():
    stem = "How many seconds in 2 hours?"
    options = ["120 s", "3600 s", "7200 s", "1800 s"]
    res = deterministic_unit_conversion_solve(stem, options)
    assert res["verified"] is True
    assert res["selected_option_letter"] == "C"
    assert res["selected_option_text"] == "7200 s"

def test_deterministic_unit_conversion_celsius_to_fahrenheit():
    stem = "Convert 100 °C to Fahrenheit."
    options = ["180 °F", "200 °F", "212 °F", "100 °F"]
    res = deterministic_unit_conversion_solve(stem, options)
    assert res["verified"] is True
    assert res["selected_option_letter"] == "C"
    assert res["selected_option_text"] == "212 °F"

# 3. Test Deterministic Physics SI Units & Formula
def test_physics_si_unit():
    stem = "The SI unit of force is"
    options = ["Joule", "Newton", "Watt", "Pascal"]
    res = deterministic_physics_solve(stem, options)
    assert res["verified"] is True
    assert res["selected_option_letter"] == "B"
    assert res["selected_option_text"] == "Newton"

def test_physics_force_calculation():
    stem = "A body has mass of 5 kg and acceleration of 2 m/s^2. What is the force?"
    options = ["5 N", "7 N", "10 N", "2.5 N"]
    res = deterministic_physics_solve(stem, options)
    assert res["verified"] is True
    assert res["selected_option_letter"] == "C"
    assert res["selected_option_text"] == "10 N"

# 4. Test Deterministic Chemistry Formula & Lookup
def test_chemistry_formula():
    stem = "What is the chemical formula of Water?"
    options = ["CO2", "H2O", "NaCl", "HCl"]
    res = deterministic_chemistry_solve(stem, options)
    assert res["verified"] is True
    assert res["selected_option_letter"] == "B"
    assert res["selected_option_text"] == "H2O"

# 5. Test Deterministic Biology Concept
def test_biology_concept():
    stem = "Which organelle is known as the powerhouse of the cell?"
    options = ["Ribosome", "Mitochondria", "Nucleus", "Lysosome"]
    res = deterministic_biology_solve(stem, options)
    assert res["verified"] is True
    assert res["selected_option_letter"] == "B"
    assert res["selected_option_text"] == "Mitochondria"

# 6. Test Ambiguity and Defect Detection
def test_ambiguity_duplicate_options():
    stem = "Which planet is known as the Red Planet?"
    options = ["Mars", "Venus", "Mars", "Jupiter"]
    res = detect_question_ambiguity_and_defects(stem, options)
    assert res["is_ambiguous"] is True
    assert "DUPLICATE_OPTIONS" in res["defects"]

def test_missing_information_defect():
    stem = "What is the value of 2x + 3 when x ="
    options = ["10", "13", "15", "8"]
    res = detect_question_ambiguity_and_defects(stem, options)
    assert res["is_ambiguous"] is True
    assert "INCOMPLETE_EQUATION_OR_PROMPT" in res["defects"]

def test_visual_dependency_defect():
    stem = "In the circuit diagram shown in the figure, what is the current through R1?"
    options = ["2 A", "4 A", "6 A", "8 A"]
    res = detect_question_ambiguity_and_defects(stem, options)
    assert "VISUAL_DEPENDENCY_DETECTED" in res["defects"]

# 7. Test Evidence-Based Confidence Engine
def test_confidence_high_deterministic_match():
    det_result = {"verified": True, "selected_option_letter": "B"}
    conf, level = calculate_evidence_based_confidence(
        solver_agrees=True,
        critic_agrees=True,
        deterministic_result=det_result,
        extraction_confidence=0.98,
        option_count=4,
        solver_answer="B"
    )
    assert conf >= 0.95
    assert level == "HIGH"

def test_confidence_penalty_on_critic_disagreement():
    det_result = {"verified": False}
    conf, level = calculate_evidence_based_confidence(
        solver_agrees=True,
        critic_agrees=False,
        deterministic_result=det_result,
        extraction_confidence=0.90,
        option_count=4,
        solver_answer="B",
        vote_agreement_ratio=0.5
    )
    assert conf < 0.70
    assert level == "UNCERTAIN"

# 8. Test End-to-End Validation: Blind Critic Agreement
def test_validate_single_question_blind_critic_agreed():
    q_data = {
        "id": "q1",
        "row_number": 1,
        "Question": "What is the capital of Australia?",
        "Option A": "Sydney",
        "Option B": "Melbourne",
        "Option C": "Canberra",
        "Option D": "Brisbane",
        "Correct Answer": "C"
    }
    with patch("app.services.ai_solver.solve_question_independently", return_value={
        "selected_option_letter": "C",
        "selected_option_text": "Canberra",
        "reasoning_summary": "Canberra is the federal capital.",
        "is_solvable": True
    }), patch("app.services.ai_solver.solve_question_blind_second_pass", return_value={
        "selected_option_letter": "C",
        "selected_option_text": "Canberra",
        "reasoning_summary": "Canberra was founded as capital.",
        "is_solvable": True
    }):
        res = validate_single_question_answer(q_data, subject="General", use_cache=False)
        assert res["validation_status"] == "AI_VALIDATED"
        assert res["ai_answer"] == "C"
        assert res["signals"]["critic_agreed"] is True
        assert "AI_BLIND_CRITIC_AGREED" in res["validation_methods"]
        assert res["answer_match"] is True

# 9. Test End-to-End Validation: Blind Critic Disagreement Triggers Self-Consistency Tiebreaker
def test_validate_disagreement_triggers_self_consistency():
    q_data = {
        "id": "q2",
        "row_number": 2,
        "Question": "Which gas is evolved when zinc reacts with dilute sulfuric acid?",
        "Option A": "Oxygen",
        "Option B": "Hydrogen",
        "Option C": "Carbon Dioxide",
        "Option D": "Nitrogen",
        "Correct Answer": "B"
    }
    # Solver says B, Blind pass says A (Disagreement), Self-consistency voting gives B with 2/3 (0.67) ratio
    with patch("app.services.ai_solver.solve_question_independently", return_value={
        "selected_option_letter": "B",
        "selected_option_text": "Hydrogen",
        "reasoning_summary": "Zn + H2SO4 -> ZnSO4 + H2.",
        "is_solvable": True
    }), patch("app.services.ai_solver.solve_question_blind_second_pass", return_value={
        "selected_option_letter": "A",
        "selected_option_text": "Oxygen",
        "reasoning_summary": "Oxygen test.",
        "is_solvable": True
    }), patch("app.services.ai_solver.solve_question_with_self_consistency", return_value={
        "selected_option_letter": "B",
        "selected_option_text": "Hydrogen",
        "reasoning_summary": "Majority vote (2/3) confirmed Hydrogen gas.",
        "vote_agreement_ratio": 0.67,
        "votes": {"B": 2, "A": 1},
        "is_solvable": True
    }):
        res = validate_single_question_answer(q_data, subject="Chemistry", use_cache=False)
        assert res["signals"]["critic_agreed"] is False
        assert "SELF_CONSISTENCY_MAJORITY_VOTE" in res["validation_methods"]
        assert res["ai_answer"] == "B"
        assert res["signals"]["vote_agreement_ratio"] == 0.67

# 10. Test Answer Conflict Detection (Source != AI)
def test_validate_answer_conflict():
    q_data = {
        "id": "q3",
        "row_number": 3,
        "Question": "What is 10 + 15?",
        "Option A": "20",
        "Option B": "25",
        "Option C": "30",
        "Option D": "35",
        "Correct Answer": "A"  # Erroneous source
    }
    res = validate_single_question_answer(q_data, subject="Mathematics", use_cache=False)
    assert res["validation_status"] == "ANSWER_CONFLICT"
    assert res["source_answer"] == "A"
    assert res["ai_answer"] == "B"
    assert res["review_required"] is True
    assert res["review_priority"] == 1

# 11. Test Visual Dependency Defect
def test_validate_visual_dependency():
    q_data = {
        "id": "q_vis",
        "row_number": 4,
        "Question": "From the velocity-time graph shown in the figure, calculate acceleration.",
        "Option A": "10 m/s^2",
        "Option B": "20 m/s^2",
        "Option C": "30 m/s^2",
        "Option D": "40 m/s^2",
        "Correct Answer": "B"
    }
    with patch("app.services.ai_solver.solve_question_independently", return_value={
        "selected_option_letter": "B",
        "selected_option_text": "20 m/s^2",
        "reasoning_summary": "Read from graph.",
        "is_solvable": True
    }), patch("app.services.ai_solver.solve_question_blind_second_pass", return_value={
        "selected_option_letter": "B",
        "selected_option_text": "20 m/s^2",
        "reasoning_summary": "Read from graph.",
        "is_solvable": True
    }):
        res = validate_single_question_answer(q_data, subject="Physics", use_cache=False)
        assert res["validation_status"] == "VISUAL_CONTEXT_REQUIRED"
        assert res["review_required"] is True
        assert res["review_priority"] == 4
        assert res["confidence"] < 0.70

# 12. Test Calibration Logging Hook
def test_calibration_logging_hook(tmp_path):
    q_data = {
        "id": "q_calib_1",
        "row_number": 5,
        "Question": "What is the capital of Italy?",
        "Option A": "Rome",
        "Option B": "Milan",
        "Option C": "Naples",
        "Option D": "Turin",
        "Correct Answer": "A"
    }
    calib_file = Path("storage/calibration_log.jsonl")
    if calib_file.exists():
        calib_file.unlink()

    with patch("app.config.settings.confidence_calibration_log", True), \
         patch("app.services.ai_solver.solve_question_independently", return_value={
             "selected_option_letter": "A",
             "selected_option_text": "Rome",
             "reasoning_summary": "Rome is the capital of Italy.",
             "is_solvable": True
         }), \
         patch("app.services.ai_solver.solve_question_blind_second_pass", return_value={
             "selected_option_letter": "A",
             "selected_option_text": "Rome",
             "reasoning_summary": "Rome is the capital.",
             "is_solvable": True
         }):
        res = validate_single_question_answer(q_data, subject="General", use_cache=False)
        assert calib_file.exists()
        lines = calib_file.read_text(encoding="utf-8").strip().splitlines()
        last_entry = json.loads(lines[-1])
        assert last_entry["question_id"] == "q_calib_1"
        assert "confidence_score" in last_entry
        assert "signals" in last_entry
