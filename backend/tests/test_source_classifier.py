import pytest
from app.services.source_classifier import classify_page_content

def test_classify_question_page():
    """Verify that a page containing questions and options is classified as QUESTION_SOURCE."""
    text = """
    SECTION A: MATHEMATICS
    1. Solve for x: x^2 - 5x + 6 = 0
    (A) 2, 3
    (B) 1, 5
    (C) -2, -3
    (D) 4, 1
    
    Q2. Find the derivative of sin(x).
    A) cos(x)
    B) -cos(x)
    C) tan(x)
    D) sec(x)
    """
    res = classify_page_content(text, page_number=1, filename="math_questions.pdf")
    assert res["role"] == "QUESTION_SOURCE"
    assert res["confidence_label"] == "HIGH"
    assert 1 in res["question_numbers"]
    assert 2 in res["question_numbers"]

def test_classify_answer_page():
    """Verify that a page containing discrete answer keys is classified as ANSWER_SOURCE."""
    text = """
    ANSWERS KEY & SOLUTIONS
    1. A
    2. B
    3. C
    4. D
    5. A
    """
    res = classify_page_content(text, page_number=4, filename="answer_key.pdf")
    assert res["role"] == "ANSWER_SOURCE"
    assert res["confidence_label"] == "HIGH"
    assert 1 in res["answer_numbers"]
    assert 5 in res["answer_numbers"]

def test_classify_mixed_page():
    """Verify that a page containing questions with inline answers is classified as MIXED_SOURCE."""
    text = """
    Q1. What is 2 + 2?
    A) 3
    B) 4
    C) 5
    D) 6
    Correct Answer: B
    
    Q2. What is 3 * 3?
    A) 6
    B) 9
    C) 12
    Answer: Option B
    """
    res = classify_page_content(text, page_number=1, filename="mixed_sheet.pdf")
    assert res["role"] == "MIXED_SOURCE"
    assert 1 in res["question_numbers"]
