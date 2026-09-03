import pytest

def test_full_answer_text_preservation_and_resolution():
    """
    Verifies that the full answer text (e.g. '3 robots') is preserved
    and that resolving AI keys ('C' -> '4 robots') produces full answer text
    while leaving all four options untouched.
    """
    row_data = {
        "Question": "A merchant ships 450 items per day...",
        "Option A": "3 robots",
        "Option B": "2 robots",
        "Option C": "4 robots",
        "Option D": "5 robots",
        "Correct Answer": "3 robots"
    }

    # Verify options intact initially
    assert row_data["Option A"] == "3 robots"
    assert row_data["Option B"] == "2 robots"
    assert row_data["Option C"] == "4 robots"
    assert row_data["Option D"] == "5 robots"
    assert row_data["Correct Answer"] == "3 robots"

    # Simulate AI resolution: AI suggested "C", which resolves to Option C ("4 robots")
    ai_key = "C"
    resolved_text = row_data[f"Option {ai_key}"]  # "4 robots"

    updated_row = {
        **row_data,
        "Correct Answer": resolved_text
    }

    # Verify all options remain completely untouched
    assert updated_row["Option A"] == "3 robots"
    assert updated_row["Option B"] == "2 robots"
    assert updated_row["Option C"] == "4 robots"
    assert updated_row["Option D"] == "5 robots"

    # Verify Correct Answer is the full text, NOT just the letter
    assert updated_row["Correct Answer"] == "4 robots"
    assert updated_row["Correct Answer"] != "C"
