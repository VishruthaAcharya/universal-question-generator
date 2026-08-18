from pathlib import Path
import pandas as pd

REQUIRED_COLUMNS = [
    "Question", "Question Topic", "Sub Topic",
    "Answer 1", "Answer 2", "Answer 3", "Answer 4",
    "Difficulty Level", "Correct Answer", "Score"
]

def read_template(path: str) -> list[str]:
    p = Path(path)
    if p.suffix.lower() == ".csv":
        df = pd.read_csv(path, nrows=0)
    elif p.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path, nrows=0)
    else:
        raise ValueError("Template must be CSV or XLSX")

    columns = [str(c) for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        raise ValueError("Template is missing required columns: " + ", ".join(missing))
    return columns
