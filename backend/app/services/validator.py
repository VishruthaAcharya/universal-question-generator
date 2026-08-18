from app.schemas.question import Question

def validate_question(data: dict) -> list[str]:
    errors = []
    try:
        q = Question.model_validate(data)
        if len({q.answer_1, q.answer_2, q.answer_3, q.answer_4}) != 4:
            errors.append("All four options must be unique.")
    except Exception as exc:
        errors.append(str(exc))
    return errors

def validate_questions(questions: list[dict]) -> list[dict]:
    results = []
    for i, q in enumerate(questions, start=1):
        errors = validate_question(q)
        results.append({"index": i, "valid": not errors, "errors": errors})
    return results
