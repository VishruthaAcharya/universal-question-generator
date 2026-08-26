import io
import pandas as pd
from app.services.template import read_template_schema, normalize_header, normalize_field_name
from app.services.validator import validate_compatibility, validate_question_row

def test_normalize_header():
    # Test normalization of header names
    assert normalize_header("\ufeffQuestion") == "question"
    assert normalize_header("Question") == "question"
    assert normalize_header(" question ") == "question"
    assert normalize_header("QUESTION") == "question"
    assert normalize_header("Difficulty Level") == "difficultylevel"

def test_normalize_field_name():
    # Test field name mapping
    assert normalize_field_name("\ufeffQuestion") == "question"
    assert normalize_field_name("Question Text") == "question"
    assert normalize_field_name("Correct Answer") == "correct_answer"
    assert normalize_field_name("Difficulty Level") == "difficulty"
    assert normalize_field_name("Score") == "score"

def test_template_compatibility_cases(tmp_path):
    # Setup template schema
    template_schema = {
        "columns": [
            "Question", "Question Topic", "Sub Topic", "Answer 1", "Answer 2",
            "Answer 3", "Answer 4", "Correct Answer", "Difficulty Level", "Score"
        ],
        "column_schema": [
            {"original_name": "Question", "normalized_name": "question", "required": True},
            {"original_name": "Question Topic", "normalized_name": "topic", "required": False},
            {"original_name": "Sub Topic", "normalized_name": "subtopic", "required": False},
            {"original_name": "Answer 1", "normalized_name": "option_1", "required": True},
            {"original_name": "Answer 2", "normalized_name": "option_2", "required": True},
            {"original_name": "Answer 3", "normalized_name": "option_3", "required": True},
            {"original_name": "Answer 4", "normalized_name": "option_4", "required": True},
            {"original_name": "Correct Answer", "normalized_name": "correct_answer", "required": True},
            {"original_name": "Difficulty Level", "normalized_name": "difficulty", "required": False},
            {"original_name": "Score", "normalized_name": "score", "required": False}
        ]
    }

    # 1. Normal UTF-8 CSV source
    q_normal = {
        "Question": "What is 1+1?",
        "Question Topic": "Math",
        "Sub Topic": "Arithmetic",
        "Answer 1": "1",
        "Answer 2": "2",
        "Answer 3": "3",
        "Answer 4": "4",
        "Correct Answer": "2",
        "Difficulty Level": "Easy",
        "Score": "1"
    }
    report = validate_compatibility(template_schema, [q_normal])
    assert report["compatible"] is True
    assert len(report["errors"]) == 0

    # 2. UTF-8 BOM CSV source (simulated via headers with BOM)
    q_bom = {
        "\ufeffQuestion": "What is 1+1?",
        "Question Topic": "Math",
        "Sub Topic": "Arithmetic",
        "Answer 1": "1",
        "Answer 2": "2",
        "Answer 3": "3",
        "Answer 4": "4",
        "Correct Answer": "2",
        "Difficulty Level": "Easy",
        "Score": "1"
    }
    report = validate_compatibility(template_schema, [q_bom])
    assert report["compatible"] is True

    # 3. Leading/trailing spaces in headers
    q_spaces = {
        " Question ": "What is 1+1?",
        "Question Topic ": "Math",
        "Sub Topic": "Arithmetic",
        "Answer 1": "1",
        "Answer 2": "2",
        "Answer 3": "3",
        "Answer 4": "4",
        "Correct Answer": "2",
        "Difficulty Level": "Easy",
        "Score": "1"
    }
    report = validate_compatibility(template_schema, [q_spaces])
    assert report["compatible"] is True

    # 4. Case differences in headers
    q_case = {
        "question": "What is 1+1?",
        "QUESTION TOPIC": "Math",
        "sub topic": "Arithmetic",
        "answer 1": "1",
        "answer 2": "2",
        "answer 3": "3",
        "answer 4": "4",
        "correct answer": "2",
        "difficulty level": "Easy",
        "score": "1"
    }
    report = validate_compatibility(template_schema, [q_case])
    assert report["compatible"] is True

    # 5. Schema validation should succeed even with empty cell values
    q_empty_cells = {
        "Question": "What is 1+1?",
        "Question Topic": "", # empty Topic
        "Sub Topic": "",      # empty Sub Topic
        "Answer 1": "1",
        "Answer 2": "2",
        "Answer 3": "3",
        "Answer 4": "4",
        "Correct Answer": "2",
        "Difficulty Level": "", # empty Difficulty
        "Score": ""           # empty Score
    }
    report = validate_compatibility(template_schema, [q_empty_cells])
    assert report["compatible"] is True
    assert len(report["errors"]) == 0

    # 6. Check that cell-value validations are correctly isolated (Data Errors)
    row_errors = validate_question_row(q_empty_cells, template_schema)
    assert len(row_errors) == 0 # optional empty cells are valid data

    # 7. Invalid cell values should trigger row/data errors, NOT compatibility schema errors
    q_invalid_cells = dict(q_normal)
    q_invalid_cells["Difficulty Level"] = "Very Difficult" # invalid difficulty value
    
    # Structure remains 100% compatible
    report_invalid = validate_compatibility(template_schema, [q_invalid_cells])
    assert report_invalid["compatible"] is True
    
    # Cell value check fails
    cell_errors = validate_question_row(q_invalid_cells, template_schema)
    assert len(cell_errors) == 1
    assert "Difficulty must be one of" in cell_errors[0]
