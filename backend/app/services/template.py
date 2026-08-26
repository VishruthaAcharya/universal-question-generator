from pathlib import Path
import pandas as pd
from typing import Any

NORMALIZATION_MAP = {
    "question": "question",
    "questiontext": "question",
    "problemstatement": "question",
    
    "questiontopic": "topic",
    "topic": "topic",
    "subject": "topic",
    
    "subtopic": "subtopic",
    
    "answer1": "option_1",
    "optiona": "option_1",
    "option1": "option_1",
    
    "answer2": "option_2",
    "optionb": "option_2",
    "option2": "option_2",
    
    "answer3": "option_3",
    "optionc": "option_3",
    "option3": "option_3",
    
    "answer4": "option_4",
    "optiond": "option_4",
    "option4": "option_4",
    
    "correctanswer": "correct_answer",
    "answer": "correct_answer",
    "correctoption": "correct_answer",
    
    "startercode": "starter_code",
    "startingcode": "starter_code",
    "codetemplate": "starter_code",
    
    "expectedoutput": "expected_output",
    "output": "expected_output",
    
    "testcases": "test_cases",
    "testcase": "test_cases",
    
    "difficultylevel": "difficulty",
    "difficulty": "difficulty",
    
    "score": "score",
    "marks": "score",
    "mark": "score"
}

from functools import lru_cache

REQUIRED_CORE_FIELDS = {"question", "correct_answer", "starter_code", "test_cases", "option_1", "option_2", "option_3", "option_4"}

def normalize_header(name: str) -> str:
    """
    Cleans and normalizes header name to strip BOM, trailing/leading whitespace,
    repeated whitespace, and lowercase.
    """
    if not isinstance(name, str):
        name = str(name)
    cleaned = name.lstrip("\ufeff")
    cleaned = "".join(cleaned.split()).lower()
    return cleaned

@lru_cache(maxsize=1024)
def normalize_field_name(name: str) -> str:
    cleaned = normalize_header(name)
    return NORMALIZATION_MAP.get(cleaned, cleaned)

def read_template_schema(path: str) -> dict[str, Any]:
    p = Path(path)
    suffix = p.suffix.lower()
    sheet_name = None

    if suffix == ".csv":
        df = pd.read_csv(path, encoding="utf-8-sig")
    elif suffix in {".xlsx", ".xls"}:
        excel_file = pd.ExcelFile(path)
        sheet_name = excel_file.sheet_names[0]
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
    else:
        raise ValueError("Template must be CSV or XLSX")

    # Clean columns: strip BOM and surrounding whitespace
    df.columns = [str(c).lstrip("\ufeff").strip() for c in df.columns]
    columns = list(df.columns)
    
    # Verify and log root cause during development (Section 10)
    if len(columns) > 0:
        raw_first = str(columns[0])
        norm_first = normalize_header(raw_first)
        # Note: If it had a BOM, df.columns clean above would have stripped it, but for test/verification:
        print(f"RAW FIRST HEADER: {repr(raw_first)}")
        print(f"NORMALIZED FIRST HEADER: {repr(norm_first)}")
    
    # Analyze columns
    column_schema = []
    for col in columns:
        normalized = normalize_field_name(col)
        # Check if mandatory
        is_required = normalized in REQUIRED_CORE_FIELDS
        
        # Check example values
        example_val = None
        if not df.empty:
            non_null = df[col].dropna()
            if not non_null.empty:
                example_val = str(non_null.iloc[0])

        column_schema.append({
            "original_name": col,
            "normalized_name": normalized,
            "required": is_required,
            "example_value": example_val
        })

    return {
        "original_filename": p.name,
        "sheet_name": sheet_name,
        "columns": columns,
        "column_schema": column_schema,
        "has_examples": len(df) > 0
    }
