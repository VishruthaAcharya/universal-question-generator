from unittest.mock import patch
import tempfile
from pathlib import Path
from app.services.source_parser import parse_source_document

def test_parse_source_document_text(tmp_path):
    p = tmp_path / "questions.txt"
    p.write_text("""
1. What is the value of pi?
A) 3.14
B) 2.71
C) 1.41
D) 1.73
Correct Answer: A
Topic: Geometry
Difficulty: Easy
""", encoding="utf-8")

    questions = parse_source_document(str(p))
    assert len(questions) == 1
    assert "value of pi" in questions[0]["question"]
    assert questions[0]["correct_answer"] == "A"
    assert questions[0]["options"][0] == "3.14"

def test_parse_source_document_csv(tmp_path):
    p = tmp_path / "questions.csv"
    p.write_text("""Question,Option 1,Option 2,Option 3,Option 4,Correct Answer,Topic,Difficulty
What is H2O?,Water,Hydrogen,Oxygen,Helium,Water,Chemistry,Easy
""", encoding="utf-8")

    questions = parse_source_document(str(p))
    assert len(questions) == 1
    assert questions[0]["question"] == "What is H2O?"
    assert questions[0]["options"] == ["Water", "Hydrogen", "Oxygen", "Helium"]
    assert questions[0]["correct_answer"] == "Water"
