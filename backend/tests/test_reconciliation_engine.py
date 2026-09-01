import pytest
from app.services.reconciliation_engine import reconcile_questions_and_answers, detect_duplicate_questions

def test_explicit_numbering_match():
    """Verify that questions and answers are matched via explicit question number."""
    questions = [
        {"question_id": "Q_001", "question_number": 1, "question": "What is 2+2?", "options": ["3", "4", "5", "6"]},
        {"question_id": "Q_002", "question_number": 2, "question": "What is 3+3?", "options": ["5", "6", "7", "8"]}
    ]
    answers = [
        {"question_number": 2, "answer": "6", "explanation": "3+3=6", "source_file": "ans.pdf", "source_page": 2},
        {"question_number": 1, "answer": "4", "explanation": "2+2=4", "source_file": "ans.pdf", "source_page": 2}
    ]
    
    reconciled = reconcile_questions_and_answers(questions, answers)
    
    # Q_001 should map to Option B (4)
    q1 = next(q for q in reconciled if q["question_id"] == "Q_001")
    assert q1["source_answer_key"] == "B"
    assert q1["source_answer_text"] == "4"
    assert q1["answer_mapping_method"] == "EXPLICIT"
    
    # Q_002 should map to Option B (6)
    q2 = next(q for q in reconciled if q["question_id"] == "Q_002")
    assert q2["source_answer_key"] == "B"
    assert q2["source_answer_text"] == "6"

def test_sequential_matching_fallback():
    """Verify sequential matching when question numbers are missing but order is clear."""
    questions = [
        {"question_id": "Q_001", "question_number": None, "question": "What is 2+2?", "options": ["3", "4", "5", "6"]},
        {"question_id": "Q_002", "question_number": None, "question": "What is 3+3?", "options": ["5", "6", "7", "8"]}
    ]
    answers = [
        {"question_number": None, "answer": "4", "source_file": "ans.pdf", "source_page": 2},
        {"question_number": None, "answer": "6", "source_file": "ans.pdf", "source_page": 2}
    ]
    
    reconciled = reconcile_questions_and_answers(questions, answers)
    
    q1 = next(q for q in reconciled if q["question_id"] == "Q_001")
    assert q1["source_answer_key"] == "B" # Option B is 4
    assert q1["answer_mapping_method"] == "SEQUENTIAL"
    
    q2 = next(q for q in reconciled if q["question_id"] == "Q_002")
    assert q2["source_answer_key"] == "B" # Option B is 6

def test_duplicate_option_values():
    """Verify that duplicate MCQ option values mark the question validation status as AMBIGUOUS."""
    questions = [
        {"question_id": "Q_001", "question_number": 1, "question": "Percentage change?", "options": ["6%", "4%", "5%", "6%"]}
    ]
    answers = [
        {"question_number": 1, "answer": "6%", "source_file": "ans.pdf", "source_page": 2}
    ]
    
    reconciled = reconcile_questions_and_answers(questions, answers)
    q1 = reconciled[0]
    
    assert q1["validation_status"] == "AMBIGUOUS"
    assert q1["review_required"] is True
    assert "Duplicate MCQ option values detected" in q1["warnings"]

def test_duplicate_question_detection():
    """Verify that similar questions across files are flagged as potential duplicates."""
    questions = [
        {"question_id": "Q_001", "question": "What is 2 + 2?", "source_file": "file1.pdf", "source_page": 1},
        {"question_id": "Q_002", "question": "What is 2 + 2?", "source_file": "file2.pdf", "source_page": 3}
    ]
    
    flagged = detect_duplicate_questions(questions)
    assert flagged[0]["validation_status"] == "DUPLICATE"
    assert len(flagged[0]["duplicate_warnings"]) > 0
    assert flagged[0]["duplicate_warnings"][0]["other_question_id"] == "Q_002"
