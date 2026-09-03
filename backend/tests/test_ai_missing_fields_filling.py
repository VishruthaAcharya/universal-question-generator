import pytest
from app.routes.generate import is_field_missing, is_core_question_column

def test_missing_fields_dynamic_calculation():
    """
    Test 1:
    question_topic="General", sub_topic=None
    Verifies that sub_topic is detected as missing, while question_topic="General"
    is preserved as valid data.
    """
    columns = ["Question", "Option A", "Option B", "Option C", "Option D", "Correct Answer", "Question Topic", "Sub Topic", "Difficulty"]
    core_cols = {col for col in columns if is_core_question_column(col)}

    question_data = {
        "Question": "What is the capital of France?",
        "Option A": "Paris",
        "Option B": "London",
        "Option C": "Berlin",
        "Option D": "Madrid",
        "Correct Answer": "Paris",
        "Question Topic": "General",
        "Sub Topic": None,
        "Difficulty": "Easy"
    }

    missing_fields = [
        col for col in columns
        if col not in core_cols and is_field_missing(question_data.get(col))
    ]

    assert "Sub Topic" in missing_fields, "Sub Topic was not detected as missing"
    assert "Question Topic" not in missing_fields, "Question Topic ('General') was falsely marked missing"
    assert "Difficulty" not in missing_fields, "Difficulty was falsely marked missing"

    # Simulate AI Fill response
    ai_inferred_value = "European Geography"
    new_data = dict(question_data)
    new_data["Sub Topic"] = ai_inferred_value

    assert new_data["Sub Topic"] == "European Geography", "Sub Topic was not populated"
    assert new_data["Question Topic"] == "General", "Question Topic was overwritten"


def test_populated_field_not_sent_to_ai():
    """
    Test 2:
    question_topic="General", sub_topic="Work and Time"
    Verifies that sub_topic is NOT sent to AI as missing.
    """
    columns = ["Question", "Option A", "Option B", "Option C", "Option D", "Correct Answer", "Question Topic", "Sub Topic", "Difficulty"]
    core_cols = {col for col in columns if is_core_question_column(col)}

    question_data = {
        "Question": "If 5 workers complete a job in 10 days...",
        "Option A": "2 days",
        "Option B": "4 days",
        "Option C": "6 days",
        "Option D": "8 days",
        "Correct Answer": "4 days",
        "Question Topic": "General",
        "Sub Topic": "Work and Time",
        "Difficulty": "Medium"
    }

    missing_fields = [
        col for col in columns
        if col not in core_cols and is_field_missing(question_data.get(col))
    ]

    assert "Sub Topic" not in missing_fields, "Populated Sub Topic was falsely marked missing"
    assert "Question Topic" not in missing_fields, "Populated Question Topic was falsely marked missing"
    assert len(missing_fields) == 0, f"Expected 0 missing fields, got: {missing_fields}"
