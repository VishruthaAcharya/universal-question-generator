import pytest
from unittest.mock import patch
from app.services.deterministic_validator import (
    deterministic_math_solve,
    deterministic_physics_solve,
    deterministic_chemistry_solve,
    deterministic_biology_solve,
    run_deterministic_validator,
    detect_subject
)
from app.services.confidence_engine import calculate_evidence_based_confidence
from app.services.ai_solver import detect_question_ambiguity_and_defects
from app.services.answer_validation_engine import (
    validate_single_question_answer,
    validate_questions_batch_answers,
    compute_question_validation_hash,
    get_cached_validation,
    save_cached_validation,
    CACHE_VERSION
)

# 1. Test Deterministic Math Solver (Arithmetic & Substitution)
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

# 2. Test Deterministic Physics SI Units & Formula
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

# 3. Test Deterministic Chemistry Formula & Lookup
def test_chemistry_formula():
    stem = "What is the chemical formula of Water?"
    options = ["CO2", "H2O", "NaCl", "HCl"]
    res = deterministic_chemistry_solve(stem, options)
    assert res["verified"] is True
    assert res["selected_option_letter"] == "B"
    assert res["selected_option_text"] == "H2O"

# 4. Test Deterministic Biology Concept
def test_biology_concept():
    stem = "Which organelle is known as the powerhouse of the cell?"
    options = ["Ribosome", "Mitochondria", "Nucleus", "Lysosome"]
    res = deterministic_biology_solve(stem, options)
    assert res["verified"] is True
    assert res["selected_option_letter"] == "B"
    assert res["selected_option_text"] == "Mitochondria"

# 5. Test Ambiguity and Defect Detection
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

# 6. Test Evidence-Based Confidence Engine
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

def test_confidence_uncertain_on_missing_info():
    det_result = {"verified": False}
    conf, level = calculate_evidence_based_confidence(
        solver_agrees=False,
        critic_agrees=False,
        deterministic_result=det_result,
        has_missing_info=True,
        solver_answer=None
    )
    assert conf < 0.70
    assert level == "UNCERTAIN"

def test_confidence_penalized_on_critic_disagreement():
    det_result = {"verified": False}
    conf, level = calculate_evidence_based_confidence(
        solver_agrees=True,
        critic_agrees=False,
        deterministic_result=det_result,
        solver_answer="A"
    )
    assert conf < 0.70
    assert level == "UNCERTAIN"

# 7. Test End-to-End Single Question Answer Validation (Match)
def test_validate_single_question_match():
    q_data = {
        "id": "q1",
        "row_number": 1,
        "Question": "What is the SI unit of force?",
        "Option A": "Joule",
        "Option B": "Newton",
        "Option C": "Watt",
        "Option D": "Pascal",
        "Correct Answer": "B"
    }
    with patch("app.services.ai_solver.solve_question_independently", return_value={
        "selected_option_letter": "B",
        "selected_option_text": "Newton",
        "reasoning_summary": "Newton is the SI unit of force.",
        "is_solvable": True
    }), patch("app.services.ai_solver.verify_with_critic", return_value={
        "agrees_with_solver": True,
        "critic_selected_letter": "B"
    }):
        res = validate_single_question_answer(q_data, subject="Physics", use_cache=False)
        assert res["ai_answer"] == "B"
        assert res["source_answer"] == "B"
        assert res["answer_match"] is True
        assert res["validation_status"] == "AI_VALIDATED"
        assert res["confidence"] >= 0.95
        assert res["review_required"] is False

# 8. Test Answer Conflict Detection (Source Answer != AI Answer)
def test_validate_single_question_conflict():
    q_data = {
        "id": "q2",
        "row_number": 2,
        "Question": "What is 15 * 8?",
        "Option A": "100",
        "Option B": "120",
        "Option C": "130",
        "Option D": "140",
        "Correct Answer": "A"  # Erroneous source key!
    }
    with patch("app.services.ai_solver.solve_question_independently", return_value={
        "selected_option_letter": "B",
        "selected_option_text": "120",
        "reasoning_summary": "15 multiplied by 8 equals 120.",
        "is_solvable": True
    }), patch("app.services.ai_solver.verify_with_critic", return_value={
        "agrees_with_solver": True,
        "critic_selected_letter": "B"
    }):
        res = validate_single_question_answer(q_data, subject="Mathematics", use_cache=False)
        assert res["ai_answer"] == "B"
        assert res["source_answer"] == "A"
        assert res["answer_match"] is False
        assert res["validation_status"] == "ANSWER_CONFLICT"
        assert res["review_required"] is True
        assert res["review_priority"] == 1

# 9. Test Visual Dependency Detection
def test_validate_visual_dependency():
    q_data = {
        "id": "q3",
        "row_number": 3,
        "Question": "As shown in the graph below, determine the velocity at t = 5s.",
        "Option A": "10 m/s",
        "Option B": "20 m/s",
        "Option C": "30 m/s",
        "Option D": "40 m/s",
        "Correct Answer": "B"
    }
    with patch("app.services.ai_solver.solve_question_independently", return_value={
        "selected_option_letter": "B",
        "selected_option_text": "20 m/s",
        "reasoning_summary": "Read from graph.",
        "is_solvable": True
    }), patch("app.services.ai_solver.verify_with_critic", return_value={
        "agrees_with_solver": True
    }):
        res = validate_single_question_answer(q_data, subject="Physics", use_cache=False)
        assert res["validation_status"] == "VISUAL_CONTEXT_REQUIRED"
        assert res["review_required"] is True
        assert res["review_priority"] == 4
        assert res["confidence"] < 0.70

# 10. Test Incomplete/OCR Corrupted Question
def test_validate_incomplete_question():
    q_data = {
        "id": "q4",
        "row_number": 4,
        "Question": "Evaluate 2x + 3 when x =",
        "Option A": "10",
        "Option B": "13",
        "Option C": "15",
        "Option D": "18",
        "Correct Answer": "B"
    }
    with patch("app.services.ai_solver.solve_question_independently", return_value={
        "selected_option_letter": None,
        "selected_option_text": None,
        "reasoning_summary": "Missing x value.",
        "is_solvable": False
    }), patch("app.services.ai_solver.verify_with_critic", return_value={
        "agrees_with_solver": False
    }):
        res = validate_single_question_answer(q_data, subject="Mathematics", use_cache=False)
        assert res["validation_status"] in ["MISSING_INFORMATION", "UNCERTAIN"]
        assert res["review_required"] is True
        assert res["confidence"] < 0.70

# 11. Test Unsolvable / Empty Response
def test_validate_unsolvable_question():
    q_data = {
        "id": "q5",
        "row_number": 5,
        "Question": "Which of the following is true?",
        "Option A": "None",
        "Option B": "None",
        "Correct Answer": ""
    }
    with patch("app.services.ai_solver.solve_question_independently", return_value={
        "selected_option_letter": None,
        "selected_option_text": None,
        "reasoning_summary": "Question cannot be determined.",
        "is_solvable": False
    }), patch("app.services.ai_solver.verify_with_critic", return_value={
        "agrees_with_solver": False
    }):
        res = validate_single_question_answer(q_data, subject="General", use_cache=False)
        assert res["validation_status"] in ["UNCERTAIN", "AMBIGUOUS"]
        assert res["review_required"] is True

# 12. Test Validation Caching
def test_validation_caching():
    stem = "What is the capital of France?"
    options = ["Berlin", "Madrid", "Paris", "Rome"]
    h = compute_question_validation_hash(stem, options, "General")
    
    mock_result = {
        "question_id": "temp_q",
        "ai_answer": "C",
        "ai_answer_text": "Paris",
        "confidence": 0.98,
        "confidence_level": "HIGH",
        "validation_status": "AI_VALIDATED",
        "reason": "Paris is the capital of France."
    }
    save_cached_validation(h, mock_result)
    
    cached = get_cached_validation(h)
    assert cached is not None
    assert cached["ai_answer"] == "C"
    assert cached["confidence"] == 0.98

# 13. Test Source Answer Immutability
def test_source_answer_immutability():
    q_data = {
        "id": "q_immut",
        "row_number": 6,
        "Question": "What is the chemical formula for Methane?",
        "Option A": "CO2",
        "Option B": "CH4",
        "Option C": "H2O",
        "Option D": "NH3",
        "Correct Answer": "A" # Wrong source
    }
    with patch("app.services.ai_solver.solve_question_independently", return_value={
        "selected_option_letter": "B",
        "selected_option_text": "CH4",
        "reasoning_summary": "Methane is CH4.",
        "is_solvable": True
    }), patch("app.services.ai_solver.verify_with_critic", return_value={
        "agrees_with_solver": True
    }):
        res = validate_single_question_answer(q_data, subject="Chemistry", use_cache=False)
        # Source answer must remain A, AI answer must be B
        assert res["source_answer"] == "A"
        assert res["ai_answer"] == "B"
        assert res["validation_status"] == "ANSWER_CONFLICT"
