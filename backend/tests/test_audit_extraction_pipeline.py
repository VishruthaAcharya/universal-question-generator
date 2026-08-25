import pytest
from app.services.symbol_normalizer import (
    normalize_math_and_greek_symbols,
    detect_unresolved_corruption
)
from app.services.mcq_integrity_validator import audit_and_validate_question
from app.services.exporter import export_to_csv, export_to_xlsx

# 1. Test Symbol Normalization on Physics/Chemistry Font Artifacts
def test_symbol_normalization():
    assert normalize_math_and_greek_symbols("2 bcF") == "2 μF"
    assert normalize_math_and_greek_symbols("Capacitor of 10 bcF connected") == "Capacitor of 10 μF connected"
    assert normalize_math_and_greek_symbols("The frequency is ac9 rad/s") == "The frequency is ω rad/s"
    assert normalize_math_and_greek_symbols("Phase difference is 90b0") == "Phase difference is 90°"
    assert normalize_math_and_greek_symbols("Cp/Cv = b3 for monoatomic gas") == "Cp/Cv = γ for monoatomic gas"
    assert normalize_math_and_greek_symbols("Resistance is 50 Ohm") == "Resistance is 50 Ω"

# 2. Test Corruption Detection Flags Malformed Tokens
def test_corruption_detection():
    # Detect replacement character
    defects = detect_unresolved_corruption("Angle of incidence is 45\ufffd")
    assert len(defects) > 0
    assert "replacement character" in defects[0].lower()

    # Detect malformed option token
    defects_token = detect_unresolved_corruption("3BC")
    assert len(defects_token) > 0

# 3. Test MCQ Integrity Validator with Exactly 4 Options and Valid Answer
def test_mcq_integrity_valid_4_options():
    q = {
        "question": "What is the unit of capacitance?",
        "options": ["Farad (F)", "Henry (H)", "Ohm (Ω)", "Weber (Wb)"],
        "correct_answer": "Farad (F)",
        "question_type": "MCQ"
    }
    audited = audit_and_validate_question(q)
    assert audited["status"] == "COMPLETE"
    assert audited["option_confidence"] == 1.0
    assert audited["answer_confidence"] >= 0.90
    assert audited["overall_confidence"] >= 0.90
    assert audited["option_a"] == "Farad (F)"
    assert audited["option_b"] == "Henry (H)"
    assert audited["option_c"] == "Ohm (Ω)"
    assert audited["option_d"] == "Weber (Wb)"

# 4. Test MCQ Integrity Validator Flags Invalid Option Count (< 4 options)
def test_mcq_integrity_invalid_option_count():
    q = {
        "question": "What is the speed of sound?",
        "options": ["340 m/s", "1500 m/s"],  # Only 2 options
        "correct_answer": "340 m/s",
        "question_type": "MCQ"
    }
    audited = audit_and_validate_question(q)
    assert audited["status"] == "REVIEW_REQUIRED"
    assert audited["option_confidence"] < 0.70
    assert any("options instead of exactly 4" in d for d in audited["extraction_defects"])

# 5. Test MCQ Integrity Validator Flags Answer Mismatch
def test_mcq_integrity_answer_mismatch():
    q = {
        "question": "Which gas is used in photosynthesis?",
        "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Argon"],
        "correct_answer": "Methane",  # Does not match any option
        "question_type": "MCQ"
    }
    audited = audit_and_validate_question(q)
    assert audited["status"] == "REVIEW_REQUIRED"
    assert audited["answer_confidence"] <= 0.50
    assert any("does not correspond" in d for d in audited["extraction_defects"])

# 6. Test 22-Question Real Regression Batch Audit & Clean Export
def test_22_question_regression_batch():
    # Simulate a realistic 22-question batch with physics/chemistry math symbols
    batch = []
    for i in range(1, 23):
        batch.append({
            "question": f"Question {i}: Calculate impedance Z when R = 10 Ohm, C = 2 bcF, frequency = ac9 rad/s, phase = 90b0, λ = 600 nm.",
            "options": [
                f"Option A for Q{i} (10 μF)",
                f"Option B for Q{i} (20 μF)",
                f"Option C for Q{i} (30 μF)",
                f"Option D for Q{i} (40 μF)"
            ],
            "correct_answer": f"Option A for Q{i} (10 μF)",
            "question_type": "MCQ"
        })

    audited_batch = [audit_and_validate_question(q) for q in batch]
    assert len(audited_batch) == 22

    # Verify all 22 questions have normalized symbols
    for q in audited_batch:
        assert "10 Ω" in q["question"]
        assert "2 μF" in q["question"]
        assert "ω rad/s" in q["question"]
        assert "90°" in q["question"]
        assert "λ" in q["question"]
        assert len(q["options"]) == 4
        assert q["status"] == "COMPLETE"
        assert q["overall_confidence"] >= 0.90

    # Export to CSV and verify
    cols = ["question", "option_a", "option_b", "option_c", "option_d", "correct_answer"]
    csv_buf = export_to_csv(audited_batch, cols)
    raw_bytes = csv_buf.getvalue()

    # Must not have BOM
    assert not raw_bytes.startswith(b"\xef\xbb\xbf")
    assert raw_bytes[0:1] == b"q"
    decoded = raw_bytes.decode("utf-8")
    assert "2 μF" in decoded
    assert "90°" in decoded
    assert "ω rad/s" in decoded
