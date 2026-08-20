from app.services.validator import validate_question_row, validate_compatibility

def test_valid_question():
    q = {
        "Question": "Q?",
        "Topic": "Physics",
        "Answer 1": "A",
        "Answer 2": "B",
        "Answer 3": "C",
        "Answer 4": "D",
        "Correct Answer": "A",
        "Difficulty": "Easy"
    }
    schema = {
        "column_schema": [
            {"original_name": "Question", "normalized_name": "question", "required": True},
            {"original_name": "Topic", "normalized_name": "topic", "required": False},
            {"original_name": "Answer 1", "normalized_name": "option_1", "required": True},
            {"original_name": "Answer 2", "normalized_name": "option_2", "required": True},
            {"original_name": "Answer 3", "normalized_name": "option_3", "required": True},
            {"original_name": "Answer 4", "normalized_name": "option_4", "required": True},
            {"original_name": "Correct Answer", "normalized_name": "correct_answer", "required": True},
            {"original_name": "Difficulty", "normalized_name": "difficulty", "required": False}
        ]
    }
    assert validate_question_row(q, schema) == []

def test_missing_required_field():
    q = {
        "Question": "",
        "Answer 1": "A",
        "Answer 2": "B",
        "Answer 3": "C",
        "Answer 4": "D",
        "Correct Answer": "A"
    }
    schema = {
        "column_schema": [
            {"original_name": "Question", "normalized_name": "question", "required": True},
            {"original_name": "Answer 1", "normalized_name": "option_1", "required": True},
            {"original_name": "Answer 2", "normalized_name": "option_2", "required": True},
            {"original_name": "Answer 3", "normalized_name": "option_3", "required": True},
            {"original_name": "Answer 4", "normalized_name": "option_4", "required": True},
            {"original_name": "Correct Answer", "normalized_name": "correct_answer", "required": True}
        ]
    }
    errors = validate_question_row(q, schema)
    assert len(errors) == 1
    assert "Question" in errors[0]
