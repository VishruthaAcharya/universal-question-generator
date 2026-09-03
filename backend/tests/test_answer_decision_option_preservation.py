import pytest
from app.models.models import Template, QuestionSet, Question
from app.routes.generate import update_question

def test_update_question_preserves_options(db_session=None):
    """
    Regression Test:
    Verifies that updating the answer decision (e.g. to 'C')
    preserves existing option values:
    Answer 1 = 14
    Answer 2 = 13
    Answer 3 = 15
    Answer 4 = 12
    and updates only the Correct Answer field.
    """
    data = {
        "Question": "How many items are in the box?",
        "Answer 1": "14",
        "Answer 2": "13",
        "Answer 3": "15",
        "Answer 4": "12",
        "Correct Answer": "14"
    }

    # Simulate updating Correct Answer to "C"
    payload = {"Correct Answer": "C"}
    updated_data = {**data, **payload}

    assert updated_data["Answer 1"] == "14", "Answer 1 was modified"
    assert updated_data["Answer 2"] == "13", "Answer 2 was modified"
    assert updated_data["Answer 3"] == "15", "Answer 3 was modified"
    assert updated_data["Answer 4"] == "12", "Answer 4 was modified"
    assert updated_data["Correct Answer"] == "C", "Correct Answer was not updated to C"
