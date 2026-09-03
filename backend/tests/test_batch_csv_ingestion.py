import pytest
import pandas as pd
from pathlib import Path
from app.services.source_parser import parse_source_batch

def test_parse_source_batch_18_row_csv(tmp_path: Path):
    """
    Regression Test for FIX 1:
    Asserts that an 18-row CSV batch-uploaded through parse_source_batch
    produces exactly 18 question objects using the dataframe extraction path.
    """
    # Build an 18-row dataframe
    rows = []
    for i in range(1, 19):
        rows.append({
            "Question": f"Sample Question {i}: What is the result of {i} + {i}?",
            "Option A": f"{i * 2}",
            "Option B": f"{i * 2 + 1}",
            "Option C": f"{i * 2 + 2}",
            "Option D": f"{i * 2 + 3}",
            "Correct Answer": f"{i * 2}",
            "Topic": "Arithmetic",
            "Difficulty": "Easy",
        })

    df = pd.DataFrame(rows)
    csv_file = tmp_path / "assessment_18_questions.csv"
    df.to_csv(csv_file, index=False, encoding="utf-8-sig")

    files_payload = [
        {
            "absolute_path": str(csv_file),
            "parent_source": None,
            "source_file": "assessment_18_questions.csv",
            "size_bytes": csv_file.stat().st_size,
        }
    ]

    result = parse_source_batch(files_payload)
    questions = result["questions"]

    assert len(questions) == 18, f"Expected exactly 18 questions from CSV batch, got {len(questions)}"
    for idx, q in enumerate(questions, start=1):
        assert f"Sample Question {idx}:" in q["question"]
        assert len(q["options"]) == 4
        assert q["correct_answer"] == str(idx * 2)
