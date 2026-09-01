import pytest
from app.services.layout_extractor import extract_questions_from_page_layout
from app.services.source_parser import merge_continued_questions

def test_mcq_with_metadata_numbered_stem():
    """MCQ with section heading + difficulty + marks, followed by a NUMBERED question stem."""
    text = """QUANTITATIVE APTITUDE
General Aptitude
MEDIUM
1 MARK
Question 1
A sum of Rs. 12,500 amounts to Rs. 15,500 in 4 years at the rate of simple interest. What is the rate of interest?
A) 3%
B) 4%
C) 5%
D) 6%
Correct Answer: 6%"""
    
    questions, _, _ = extract_questions_from_page_layout(text, page_number=1)
    
    assert len(questions) == 1
    q = questions[0]
    assert q["question_number"] == 1
    assert q["category"] == "QUANTITATIVE APTITUDE"
    assert q["topic"] == "General Aptitude"
    assert q["difficulty"] == "MEDIUM"
    assert q["marks"] == "1"
    assert q["question"] == "A sum of Rs. 12,500 amounts to Rs. 15,500 in 4 years at the rate of simple interest. What is the rate of interest?"
    assert len(q["options"]) == 4
    assert q["options"] == ["3%", "4%", "5%", "6%"]
    assert q["correct_answer"] == "6%"

def test_mcq_with_metadata_unnumbered_stem():
    """MCQ with section heading + difficulty + marks, followed by an UNNUMBERED question stem (the exact reported bug)."""
    text = """QUANTITATIVE APTITUDE
General Aptitude
MEDIUM
1 MARK
A sum of Rs. 12,500 amounts to Rs. 15,500 in 4 years at the rate of simple interest. What is the rate of interest?
A) 3%
B) 4%
C) 5%
D) 6%
Correct Answer: 6%"""

    questions, _, _ = extract_questions_from_page_layout(text, page_number=1)

    assert len(questions) == 1
    q = questions[0]
    assert q["category"] == "QUANTITATIVE APTITUDE"
    assert q["topic"] == "General Aptitude"
    assert q["difficulty"] == "MEDIUM"
    assert q["marks"] == "1"
    assert q["question"] == "A sum of Rs. 12,500 amounts to Rs. 15,500 in 4 years at the rate of simple interest. What is the rate of interest?"
    assert len(q["options"]) == 4
    assert q["options"] == ["3%", "4%", "5%", "6%"]
    assert q["correct_answer"] == "6%"

def test_normal_numbered_questions():
    """Normal numbered questions parsing."""
    text = """1. What is the capital of France?
A) London
B) Berlin
C) Paris
D) Madrid
Answer: C

2. What is 2 + 2?
A) 3
B) 4
C) 5
D) 6
Answer: B"""

    questions, _, _ = extract_questions_from_page_layout(text, page_number=1)

    assert len(questions) == 2
    assert questions[0]["question_number"] == 1
    assert questions[0]["question"] == "What is the capital of France?"
    assert questions[0]["options"] == ["London", "Berlin", "Paris", "Madrid"]
    assert questions[0]["correct_answer"] == "C"

    assert questions[1]["question_number"] == 2
    assert questions[1]["question"] == "What is 2 + 2?"
    assert questions[1]["options"] == ["3", "4", "5", "6"]
    assert questions[1]["correct_answer"] == "B"

def test_questions_split_across_pages():
    """Questions split across pages merged via merge_continued_questions."""
    # Page 1 contains incomplete question stem without options
    page1_text = """Question 1
A continuous stream of sensor data generates 1.2 TB every 8 hours. If Amazon Kinesis shards can ingest up to 1 MB/sec per shard, what is the minimum number of shards required to handle this stream without lag?"""
    
    # Page 2 contains options and continuation
    page2_text = """(1 TB = 10^6 MB)
A) 38 shards
B) 42 shards
C) 45 shards
D) 50 shards
Correct Answer: C"""

    p1_qs, _, _ = extract_questions_from_page_layout(page1_text, page_number=1)
    p2_qs, _, _ = extract_questions_from_page_layout(page2_text, page_number=2)

    assert len(p1_qs) == 1
    assert len(p2_qs) == 1

    # Simulate multi-page stitching
    p1_qs[0]["source_file"] = "test.pdf"
    p2_qs[0]["source_file"] = "test.pdf"
    all_raw = [p1_qs[0], p2_qs[0]]
    merged = merge_continued_questions(all_raw)

    assert len(merged) == 1
    assert len(merged[0]["options"]) == 4
    assert merged[0]["correct_answer"] == "C"
    assert "minimum number of shards" in merged[0]["question"]

def test_coding_questions_without_options():
    """Coding and subjective questions without MCQ options must NOT be merged."""
    text = """Question 1
Write a Python function to reverse a singly linked list in O(n) time and O(1) space.
Marks: 5

Question 2
Write a SQL query to find the second highest salary from the Employee table.
Marks: 5"""

    questions, _, _ = extract_questions_from_page_layout(text, page_number=1)

    assert len(questions) == 2
    assert questions[0]["question_number"] == 1
    assert "reverse a singly linked list" in questions[0]["question"]
    assert questions[0]["marks"] == "5"
    assert len(questions[0]["options"]) == 0

    assert questions[1]["question_number"] == 2
    assert "second highest salary" in questions[1]["question"]
    assert questions[1]["marks"] == "5"
    assert len(questions[1]["options"]) == 0

    # Verify merge_continued_questions also does not merge them
    questions[0]["source_file"] = "test.pdf"
    questions[1]["source_file"] = "test.pdf"
    merged = merge_continued_questions(questions)
    assert len(merged) == 2

def test_multiple_questions_on_one_page():
    """Multiple unnumbered questions on a single page."""
    text = """QUANTITATIVE APTITUDE
General Aptitude
MEDIUM
1 MARK
A sum of Rs. 12,500 amounts to Rs. 15,500 in 4 years at the rate of simple interest. What is the rate of interest?
A) 3%
B) 4%
C) 5%
D) 6%
Correct Answer: 6%

LOGICAL REASONING
General Aptitude
EASY
1 MARK
Find the missing number in the series: 4, 7, 12, 19, 28, ?
A) 30
B) 36
C) 39
D) 49
Correct Answer: 39"""

    questions, _, _ = extract_questions_from_page_layout(text, page_number=1)

    assert len(questions) == 2
    assert questions[0]["category"] == "QUANTITATIVE APTITUDE"
    assert questions[0]["difficulty"] == "MEDIUM"
    assert "rate of simple interest" in questions[0]["question"]
    assert len(questions[0]["options"]) == 4
    assert questions[0]["correct_answer"] == "6%"

    assert questions[1]["category"] == "LOGICAL REASONING"
    assert questions[1]["difficulty"] == "EASY"
    assert "missing number" in questions[1]["question"]
    assert len(questions[1]["options"]) == 4
    assert questions[1]["correct_answer"] == "39"

def test_question_followed_by_options():
    """Question followed immediately by options."""
    text = """Which AWS service is used for serverless compute execution?
A) AWS Lambda
B) Amazon EC2
C) Amazon ECS
D) AWS Elastic Beanstalk
Correct Answer: AWS Lambda"""

    questions, _, _ = extract_questions_from_page_layout(text, page_number=1)

    assert len(questions) == 1
    assert questions[0]["question"] == "Which AWS service is used for serverless compute execution?"
    assert len(questions[0]["options"]) == 4
    assert questions[0]["options"][0] == "AWS Lambda"
    assert questions[0]["correct_answer"] == "AWS Lambda"

def test_metadata_before_stem_with_question_number():
    """Question whose metadata appears before the stem, WITH a question number present."""
    text = """Topic: Mathematics
Difficulty: Hard
Marks: 2
Question 5
Evaluate the definite integral of x * exp(x) dx from 0 to 1.
A) 1
B) e - 1
C) 2
D) e
Correct Answer: 1"""

    questions, _, _ = extract_questions_from_page_layout(text, page_number=1)

    assert len(questions) == 1
    q = questions[0]
    assert q["question_number"] == 5
    assert q["topic"] == "Mathematics"
    assert q["difficulty"] == "HARD"
    assert q["marks"] == "2"
    assert q["question"] == "Evaluate the definite integral of x * exp(x) dx from 0 to 1."
    assert len(q["options"]) == 4
    assert q["options"] == ["1", "e - 1", "2", "e"]
    assert q["correct_answer"] == "1"
