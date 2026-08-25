import pandas as pd
from app.services.deterministic_parser import (
    extract_questions_from_structured_text,
    extract_questions_from_dataframe,
)

SAMPLE_28_QUESTIONS_TEXT = """
1. What is the standard form of a quadratic equation?
A) ax^2 + bx + c = 0
B) ax + b = 0
C) ax^3 + bx^2 + cx + d = 0
D) y = mx + c
Correct Answer: A
Topic: Quadratic Equations
Difficulty: Easy

2. Which of the following is a quadratic equation?
(A) x^2 - 4 = 0
(B) 2x + 3 = 5
(C) x^3 + 2x = 1
(D) 1/x + x = 2
Answer: A
Topic: Quadratic Equations
Difficulty: Medium

3. The discriminant of ax^2 + bx + c = 0 is given by:
A. b^2 - 4ac
B. b^2 + 4ac
C. 4ac - b^2
D. 2a - b
Ans: A
Topic: Quadratic Equations
Difficulty: Easy
"""

def test_extract_questions_from_structured_text():
    questions = extract_questions_from_structured_text(SAMPLE_28_QUESTIONS_TEXT, page_number=1)
    assert len(questions) == 3
    assert questions[0]["question"] == "What is the standard form of a quadratic equation?"
    assert len(questions[0]["options"]) == 4
    assert questions[0]["options"][0] == "ax^2 + bx + c = 0"
    assert questions[0]["correct_answer"] == "A"
    assert questions[0]["topic"] == "Quadratic Equations"
    assert questions[0]["difficulty"] == "Easy"
    assert questions[0]["source_page"] == 1

    assert questions[1]["question"] == "Which of the following is a quadratic equation?"
    assert len(questions[1]["options"]) == 4
    assert questions[1]["correct_answer"] == "A"
    assert questions[1]["difficulty"] == "Medium"

    assert questions[2]["correct_answer"] == "A"

def test_extract_questions_from_dataframe():
    df = pd.DataFrame([
        {
            "Question Text": "What is 2 + 2?",
            "Option A": "3",
            "Option B": "4",
            "Option C": "5",
            "Option D": "6",
            "Correct Answer": "B",
            "Topic": "Basic Arithmetic",
            "Difficulty Level": "Easy"
        },
        {
            "Question Text": "What is 5 * 5?",
            "Option A": "20",
            "Option B": "25",
            "Option C": "30",
            "Option D": "35",
            "Correct Answer": "B",
            "Topic": "Multiplication",
            "Difficulty Level": "Easy"
        }
    ])

    questions = extract_questions_from_dataframe(df, page_number=1)
    assert len(questions) == 2
    assert questions[0]["question"] == "What is 2 + 2?"
    assert questions[0]["options"] == ["3", "4", "5", "6"]
    assert questions[0]["correct_answer"] == "B"
    assert questions[0]["topic"] == "Basic Arithmetic"
    assert questions[0]["difficulty"] == "Easy"
