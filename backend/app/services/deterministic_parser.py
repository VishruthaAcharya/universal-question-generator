import re
from typing import Any
import pandas as pd

# Regex patterns for question headers e.g. "1.", "1)", "Q1.", "Q1:", "Question 1:", "1 -", "Q.1", "[1]"
QUESTION_HEADER_PATTERN = re.compile(
    r"^\s*(?:(?:Q(?:uestion)?[\s\.\:\-]*\d+[\.\)\:\-]?)|(?:\d+)[\.\)\:\-]|\bQ\d+\b|\[\d+\])\s+",
    re.IGNORECASE | re.MULTILINE
)

# Regex pattern for option markers e.g. "(A)", "A)", "A.", "[A]", "(a)", "a)", "a."
OPTION_START_PATTERN = re.compile(
    r"(?:^|\s+)(?:\(([A-Da-d1-4])\)|([A-Da-d1-4])[\.\)](?!/)|\[([A-Da-d1-4])\])\s+",
    re.MULTILINE
)

# Regex pattern for answer indicators
ANSWER_PATTERN = re.compile(
    r"(?:(?:Correct\s+)?Answer|Ans|Correct\s+Option|Key)\s*[\:\-\.]*\s*(?:Option\s*)?\(?([A-Da-d1-4]|True|False|[^\n\r]+?)\)?(?:\s*$|\s+(?=(?:Topic|Difficulty|Explanation|Bloom)))",
    re.IGNORECASE | re.MULTILINE
)

# Regex pattern for metadata fields
TOPIC_PATTERN = re.compile(r"Topic\s*[\:\-\.]*\s*([^\n\r]+)", re.IGNORECASE)
DIFFICULTY_PATTERN = re.compile(r"Difficulty(?:\s*Level)?\s*[\:\-\.]*\s*(Easy|Medium|Hard|Auto)", re.IGNORECASE)
SCORE_PATTERN = re.compile(r"(?:Marks?|Score)\s*[\:\-\.]*\s*(\d+(?:\.\d+)?)", re.IGNORECASE)

def parse_options_from_block(text: str) -> tuple[str, list[str], str | None]:
    """
    Given a question body text, extracts question stem, list of options, and inline answer key if present.
    """
    answer_match = ANSWER_PATTERN.search(text)
    correct_answer = None
    if answer_match:
        correct_answer = answer_match.group(1).strip()
        # Remove answer line from text for option parsing
        text_before_ans = text[:answer_match.start()]
    else:
        text_before_ans = text

    # Find all option matches
    option_matches = list(OPTION_START_PATTERN.finditer(text_before_ans))
    if not option_matches or len(option_matches) < 2:
        # Check if options are on separate lines starting with A/B/C/D
        lines = text_before_ans.split("\n")
        stem_lines = []
        options = []
        in_options = False

        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue
            opt_line_match = re.match(r"^([A-Da-d1-4])[\.\)\:\-]\s*(.*)$", trimmed)
            if opt_line_match:
                in_options = True
                options.append(opt_line_match.group(2).strip())
            elif in_options:
                if options:
                    options[-1] += " " + trimmed
            else:
                stem_lines.append(trimmed)

        if len(options) >= 2:
            return " ".join(stem_lines).strip(), options, correct_answer
        return text.strip(), [], correct_answer

    # Extract stem (text before the first option)
    stem = text_before_ans[:option_matches[0].start()].strip()

    options = []
    for idx, match in enumerate(option_matches):
        start = match.end()
        end = option_matches[idx + 1].start() if idx + 1 < len(option_matches) else len(text_before_ans)
        opt_text = text_before_ans[start:end].strip()
        if opt_text:
            options.append(opt_text)

    return stem, options, correct_answer

from app.services.answer_key_detector import is_answer_key_text

def extract_questions_from_structured_text(text: str, page_number: int | None = None) -> list[dict[str, Any]]:
    """
    Deterministically parses text to find numbered question blocks, options, and answer keys.
    Returns list of structured question dicts matching the standard extraction schema.
    If the text is an Answer Key section/page, returns empty list so it is handled by the answer key parser.
    """
    if not text or not text.strip():
        return []

    # If this page is solely an Answer Key page, do NOT extract questions from it
    if is_answer_key_text(text):
        return []

    # Clean text
    clean_text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Find question start positions
    matches = list(QUESTION_HEADER_PATTERN.finditer(clean_text))
    if not matches:
        return []

    questions = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(clean_text)
        block = clean_text[start:end].strip()

        # Extract leading question number marker from the block
        header_match = QUESTION_HEADER_PATTERN.match(block)
        q_num = idx + 1
        if header_match:
            header_str = header_match.group(0).strip()
            num_m = re.search(r"\d+", header_str)
            if num_m:
                try:
                    q_num = int(num_m.group(0))
                except ValueError:
                    q_num = num_m.group(0)
            body = block[header_match.end():].strip()
        else:
            body = block

        # Extract Topic, Difficulty, Score from block if present
        topic = None
        topic_m = TOPIC_PATTERN.search(body)
        if topic_m:
            topic = topic_m.group(1).strip()

        difficulty = None
        diff_m = DIFFICULTY_PATTERN.search(body)
        if diff_m:
            difficulty = diff_m.group(1).strip().capitalize()

        score = "1"
        score_m = SCORE_PATTERN.search(body)
        if score_m:
            score = score_m.group(1).strip()

        stem, options, correct_ans = parse_options_from_block(body)

        # Clean stem of any trailing metadata keywords
        stem = TOPIC_PATTERN.sub("", stem)
        stem = DIFFICULTY_PATTERN.sub("", stem)
        stem = SCORE_PATTERN.sub("", stem)
        stem = ANSWER_PATTERN.sub("", stem).strip()

        if stem and len(stem) >= 3:
            q_dict: dict[str, Any] = {
                "question_id": f"Q_{idx + 1:03d}",
                "question_number": q_num,
                "question": stem,
                "options": options if options else [],
                "correct_answer": correct_ans or "",
                "topic": topic or "",
                "subtopic": "",
                "difficulty": difficulty or "Medium",
                "score": score,
                "starter_code": "",
                "expected_output": "",
                "test_cases": "",
                "source_page": page_number
            }
            questions.append(q_dict)

    return questions

def extract_questions_from_dataframe(df: pd.DataFrame, page_number: int = 1) -> list[dict[str, Any]]:
    """
    Deterministically parses a DataFrame (CSV or Excel sheet) into question dicts.
    """
    if df.empty:
        return []

    col_map = {}
    for col in df.columns:
        norm = "".join(str(col).lstrip("\ufeff").split()).lower()
        col_map[norm] = col

    q_col = col_map.get("question") or col_map.get("questiontext") or col_map.get("problemstatement") or col_map.get("prompt")
    if not q_col:
        return []

    opt_cols = []
    for opt_key in ["optiona", "option1", "answer1", "optionb", "option2", "answer2", "optionc", "option3", "answer3", "optiond", "option4", "answer4"]:
        if opt_key in col_map and col_map[opt_key] not in opt_cols:
            opt_cols.append(col_map[opt_key])

    ans_col = col_map.get("correctanswer") or col_map.get("answer") or col_map.get("correctoption")
    topic_col = col_map.get("topic") or col_map.get("subject") or col_map.get("questiontopic")
    diff_col = col_map.get("difficulty") or col_map.get("difficultylevel")
    score_col = col_map.get("score") or col_map.get("marks") or col_map.get("mark")

    questions = []
    for _, row in df.iterrows():
        q_text = str(row.get(q_col, "") or "").strip()
        if not q_text or q_text.lower() == "nan":
            continue

        options = []
        for oc in opt_cols:
            oval = str(row.get(oc, "") or "").strip()
            if oval and oval.lower() != "nan":
                options.append(oval)

        ans_val = str(row.get(ans_col, "") or "").strip() if ans_col else ""
        if ans_val.lower() == "nan":
            ans_val = ""

        topic_val = str(row.get(topic_col, "") or "").strip() if topic_col else ""
        if topic_val.lower() == "nan":
            topic_val = ""

        diff_val = str(row.get(diff_col, "") or "").strip() if diff_col else "Medium"
        if diff_val.lower() == "nan":
            diff_val = "Medium"

        score_val = str(row.get(score_col, "") or "").strip() if score_col else "1"
        if score_val.lower() == "nan":
            score_val = "1"

        questions.append({
            "question": q_text,
            "options": options,
            "correct_answer": ans_val,
            "topic": topic_val,
            "subtopic": "",
            "difficulty": diff_val if diff_val in ["Easy", "Medium", "Hard"] else "Medium",
            "score": score_val,
            "starter_code": "",
            "expected_output": "",
            "test_cases": "",
            "source_page": page_number,
            # Retain original headers as keys (values can be empty but structure is retained)
            **{str(c): row.get(c, "") for c in df.columns}
        })

    return questions
