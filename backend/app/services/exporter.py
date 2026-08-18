from io import BytesIO
import pandas as pd
from app.services.template import REQUIRED_COLUMNS

FIELD_MAP = {
    "Question": "question",
    "Question Topic": "topic",
    "Sub Topic": "subtopic",
    "Answer 1": "answer_1",
    "Answer 2": "answer_2",
    "Answer 3": "answer_3",
    "Answer 4": "answer_4",
    "Difficulty Level": "difficulty",
    "Correct Answer": "correct_answer",
    "Score": "score",
}

def map_to_template(questions: list[dict], columns: list[str]) -> pd.DataFrame:
    rows = []
    for q in questions:
        rows.append({
            col: q.get(FIELD_MAP[col], "")
            for col in columns
        })
    return pd.DataFrame(rows, columns=columns)

def export_csv(questions: list[dict], columns: list[str]) -> BytesIO:
    df = map_to_template(questions, columns)
    buf = BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    return buf

def export_xlsx(questions: list[dict], columns: list[str]) -> BytesIO:
    df = map_to_template(questions, columns)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Questions")
        ws = writer.book["Questions"]
        ws.freeze_panes = "A2"
        for cell in ws[1]:
            cell.font = cell.font.copy(bold=True)
    buf.seek(0)
    return buf
