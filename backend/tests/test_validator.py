from app.services.validator import validate_question

def base():
    return {
        "question": "Q?",
        "topic": "Physics",
        "subtopic": "Test",
        "answer_1": "A",
        "answer_2": "B",
        "answer_3": "C",
        "answer_4": "D",
        "difficulty": "Easy",
        "correct_answer": "A",
        "score": 1,
    }

def test_valid_question():
    assert validate_question(base()) == []

def test_wrong_answer_fails():
    q = base()
    q["correct_answer"] = "X"
    assert validate_question(q)

def test_duplicate_options_fail():
    q = base()
    q["answer_4"] = "A"
    assert validate_question(q)
