from app.services.exporter import map_to_template
from app.services.template import REQUIRED_COLUMNS

def test_mapping():
    q = {
        "question": "Q", "topic": "T", "subtopic": "S",
        "answer_1": "A", "answer_2": "B", "answer_3": "C", "answer_4": "D",
        "difficulty": "Easy", "correct_answer": "A", "score": 1
    }
    df = map_to_template([q], REQUIRED_COLUMNS)
    assert list(df.columns) == REQUIRED_COLUMNS
    assert df.iloc[0]["Correct Answer"] == "A"
