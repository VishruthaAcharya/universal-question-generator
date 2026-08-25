import pytest
from unittest.mock import patch
from app.services.answer_key_detector import (
    is_answer_key_text,
    extract_answer_key_entries,
)
from app.services.cross_page_mapper import map_cross_page_answers
from app.services.source_parser import parse_source_document

# 1. Test "Answer Key" Heading and Entry Detection
def test_answer_key_heading_and_discrete_entries():
    text = """
    ANSWER KEY
    1. B
    2. D
    3. A
    4. C
    """
    assert is_answer_key_text(text) is True
    entries = extract_answer_key_entries(text, page_number=20)
    assert len(entries) == 4
    assert entries[0]["question_number"] == 1
    assert entries[0]["answer"] == "B"
    assert entries[0]["source_page"] == 20
    assert entries[3]["question_number"] == 4
    assert entries[3]["answer"] == "C"

# 2. Test "Answers" Heading Detection and Q1 - A format
def test_answers_heading_and_q_dash_format():
    text = """
    Answers:
    Q1 - A
    Q2 - C
    Q3 - B
    Q4 - D
    """
    assert is_answer_key_text(text) is True
    entries = extract_answer_key_entries(text, page_number=100)
    assert len(entries) == 4
    assert entries[0]["question_number"] == 1
    assert entries[0]["answer"] == "A"
    assert entries[0]["source_page"] == 100

# 3. Test Compact Comma Separated Format: "1-A, 2-B, 3-C, 4-D"
def test_compact_comma_separated_format():
    text = """
    SOLUTIONS
    1-A, 2-B, 3-C, 4-D, 5-A
    """
    assert is_answer_key_text(text) is True
    entries = extract_answer_key_entries(text, page_number=80)
    assert len(entries) == 5
    assert entries[0]["question_number"] == 1
    assert entries[0]["answer"] == "A"
    assert entries[4]["question_number"] == 5
    assert entries[4]["answer"] == "A"

# 4. Test Parenthesis and Bracket Formats: "1) A", "2) C", "[3] B"
def test_parenthesis_and_bracket_formats():
    text = """
    Correct Options
    1) A
    2) C
    [3] B
    (4) D
    """
    assert is_answer_key_text(text) is True
    entries = extract_answer_key_entries(text, page_number=15)
    assert len(entries) == 4
    assert entries[0]["answer"] == "A"
    assert entries[1]["answer"] == "C"
    assert entries[2]["answer"] == "B"
    assert entries[3]["answer"] == "D"

# 5. Test Range Grouped Format: "1-10: A B C D A B C D A B"
def test_range_grouped_answer_key():
    text = """
    Answer Sheet
    1-5: B, D, A, C, A
    6-10: C B D A B
    """
    assert is_answer_key_text(text) is True
    entries = extract_answer_key_entries(text, page_number=50)
    assert len(entries) == 10
    assert entries[0]["question_number"] == 1
    assert entries[0]["answer"] == "B"
    assert entries[4]["question_number"] == 5
    assert entries[4]["answer"] == "A"
    assert entries[5]["question_number"] == 6
    assert entries[5]["answer"] == "C"
    assert entries[9]["question_number"] == 10
    assert entries[9]["answer"] == "B"

# 6. Test Cross-Page Mapping (Questions on Page 1-10, Answers on Page 20)
def test_cross_page_mapping_remote_page():
    questions = [
        {"question_number": 1, "question": "What is the SI unit of force?", "options": ["Joule", "Newton", "Watt", "Pascal"], "source_page": 2},
        {"question_number": 2, "question": "What is the capital of France?", "options": ["Berlin", "Madrid", "Paris", "Rome"], "source_page": 5},
        {"question_number": 3, "question": "What is 2 + 2?", "options": ["3", "4", "5", "6"], "source_page": 8},
    ]
    answer_entries = [
        {"question_number": 1, "answer": "B", "source_page": 20, "source_section": "Answer Key", "source_type": "EXPLICIT_ANSWER_KEY"},
        {"question_number": 2, "answer": "C", "source_page": 20, "source_section": "Answer Key", "source_type": "EXPLICIT_ANSWER_KEY"},
        {"question_number": 3, "answer": "B", "source_page": 20, "source_section": "Answer Key", "source_type": "EXPLICIT_ANSWER_KEY"},
    ]
    mapped = map_cross_page_answers(questions, answer_entries)
    assert len(mapped) == 3
    assert mapped[0]["source_answer"] == "B"
    assert mapped[0]["answer_page"] == 20
    assert mapped[0]["answer_source"] == "EXPLICIT_ANSWER_KEY"
    assert mapped[0]["mapping_confidence"] >= 0.95
    assert mapped[1]["source_answer"] == "C"
    assert mapped[1]["answer_page"] == 20
    assert mapped[2]["source_answer"] == "B"
    assert mapped[2]["answer_page"] == 20

# 7. Test Partial Answer Key (Questions 1-5, Answer Key has only 1-3)
def test_partial_answer_key_mapping():
    questions = [
        {"question_number": 1, "question": "Q1?", "source_page": 10},
        {"question_number": 2, "question": "Q2?", "source_page": 10},
        {"question_number": 3, "question": "Q3?", "source_page": 11},
        {"question_number": 4, "question": "Q4?", "source_page": 11},
        {"question_number": 5, "question": "Q5?", "source_page": 12},
    ]
    answer_entries = [
        {"question_number": 1, "answer": "A", "source_page": 50, "source_type": "EXPLICIT_ANSWER_KEY"},
        {"question_number": 2, "answer": "C", "source_page": 50, "source_type": "EXPLICIT_ANSWER_KEY"},
        {"question_number": 3, "answer": "B", "source_page": 50, "source_type": "EXPLICIT_ANSWER_KEY"},
    ]
    mapped = map_cross_page_answers(questions, answer_entries)
    assert mapped[0]["source_answer"] == "A"
    assert mapped[0]["answer_mapping_status"] == "ANSWER_MAPPED"
    assert mapped[1]["source_answer"] == "C"
    assert mapped[2]["source_answer"] == "B"
    # Questions 4 & 5 must be marked as missing without inventing answers
    assert mapped[3]["source_answer"] is None
    assert mapped[3]["answer_source"] == "MISSING"
    assert mapped[3]["answer_mapping_status"] == "MISSING_ANSWER"
    assert mapped[4]["source_answer"] is None
    assert mapped[4]["answer_source"] == "MISSING"

# 8. Test Missing Answer Key (Zero answers detected)
def test_missing_answer_key_no_hallucination():
    questions = [
        {"question_number": 1, "question": "What is the speed of light?", "source_page": 1},
        {"question_number": 2, "question": "What is water?", "source_page": 2},
    ]
    mapped = map_cross_page_answers(questions, [])
    assert mapped[0]["source_answer"] is None
    assert mapped[0]["answer_source"] == "MISSING"
    assert mapped[0]["answer_mapping_status"] == "MISSING_ANSWER"
    assert mapped[1]["source_answer"] is None

# 9. Test Repeated Question Numbers Across Chapters (Disambiguated)
def test_repeated_question_numbers_chapter_disambiguation():
    questions = [
        {"question_number": 1, "question": "Kinematics Q1", "source_chapter": "Chapter 1: Kinematics", "source_page": 5},
        {"question_number": 2, "question": "Kinematics Q2", "source_chapter": "Chapter 1: Kinematics", "source_page": 6},
        {"question_number": 1, "question": "Optics Q1", "source_chapter": "Chapter 2: Optics", "source_page": 25},
        {"question_number": 2, "question": "Optics Q2", "source_chapter": "Chapter 2: Optics", "source_page": 26},
    ]
    answer_entries = [
        {"question_number": 1, "answer": "A", "source_chapter": "Chapter 1: Kinematics", "source_page": 90, "source_type": "EXPLICIT_ANSWER_KEY"},
        {"question_number": 2, "answer": "B", "source_chapter": "Chapter 1: Kinematics", "source_page": 90, "source_type": "EXPLICIT_ANSWER_KEY"},
        {"question_number": 1, "answer": "D", "source_chapter": "Chapter 2: Optics", "source_page": 90, "source_type": "EXPLICIT_ANSWER_KEY"},
        {"question_number": 2, "answer": "C", "source_chapter": "Chapter 2: Optics", "source_page": 90, "source_type": "EXPLICIT_ANSWER_KEY"},
    ]
    mapped = map_cross_page_answers(questions, answer_entries)
    # Chapter 1 Q1 -> A
    assert mapped[0]["source_answer"] == "A"
    assert mapped[0]["answer_mapping_status"] == "ANSWER_MAPPED"
    # Chapter 1 Q2 -> B
    assert mapped[1]["source_answer"] == "B"
    # Chapter 2 Q1 -> D
    assert mapped[2]["source_answer"] == "D"
    assert mapped[2]["answer_mapping_status"] == "ANSWER_MAPPED"
    # Chapter 2 Q2 -> C
    assert mapped[3]["source_answer"] == "C"

# 10. Test Repeated Question Numbers Without Chapter Context (Ambiguous Mapping)
def test_ambiguous_repeated_question_numbers():
    questions = [
        {"question_number": 1, "question": "Test Q1", "source_page": 5},
    ]
    answer_entries = [
        {"question_number": 1, "answer": "A", "source_chapter": "Section 1", "source_page": 90},
        {"question_number": 1, "answer": "D", "source_chapter": "Section 2", "source_page": 90},
    ]
    mapped = map_cross_page_answers(questions, answer_entries)
    assert mapped[0]["answer_mapping_status"] == "AMBIGUOUS_MAPPING"
    assert mapped[0]["review_required"] is True
    assert mapped[0]["mapping_confidence"] < 0.70

# 11. Test Full Multi-Page Document Parse (Questions on p.1-2, Answer Key on p.3)
def test_full_document_cross_page_parsing(tmp_path):
    p = tmp_path / "assessment.txt"
    p.write_text("""
1. What is 5 + 7?
A) 10
B) 12
C) 14
D) 16

2. What is the capital of Japan?
A) Seoul
B) Beijing
C) Tokyo
D) Bangkok

3. Which gas do plants absorb?
A) Oxygen
B) Nitrogen
C) Carbon Dioxide
D) Helium

ANSWER KEY
1. B
2. C
3. C
""", encoding="utf-8")

    questions = parse_source_document(str(p))
    assert len(questions) == 3
    assert questions[0]["question_number"] == 1
    assert questions[0]["source_answer"] == "B"
    assert questions[0]["answer_source"] == "EXPLICIT_ANSWER_KEY"
    assert questions[0]["mapping_confidence"] >= 0.95
    assert questions[1]["question_number"] == 2
    assert questions[1]["source_answer"] == "C"
    assert questions[2]["question_number"] == 3
    assert questions[2]["source_answer"] == "C"
