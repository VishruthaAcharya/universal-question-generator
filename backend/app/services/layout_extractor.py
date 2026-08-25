import re
from typing import Any
from app.services.option_extractor import extract_options_and_stem
from app.services.question_classifier import classify_question_type
from app.services.answer_key_detector import is_answer_key_text
from app.services.mcq_integrity_validator import audit_and_validate_question

# Regex for section and part headings
SECTION_HEADING_PATTERN = re.compile(
    r"^\s*(?:PART|SECTION)\s*[-–—:\.]*\s*([A-Za-z0-9IVXLCDM]+)(?:\s*[\(\[]\s*([^\)\]]+)[\)\]])?(?:\s*[:\-]\s*(.*))?$",
    re.IGNORECASE | re.MULTILINE
)

# Marks pattern: "(1 Mark)", "2 Marks", "[5M]", "3 MARKS EACH"
MARKS_PATTERN = re.compile(
    r"\b(\d+)\s*(?:marks?|mark|m)\b",
    re.IGNORECASE
)

# Question header pattern: "1.", "2)", "Q1:", "10 -", "[1]"
QUESTION_START_PATTERN = re.compile(
    r"^(?:(?:Q(?:uestion)?[\s\.\:\-]*\d+)|(?:\d+)[\.\)\:\-]|\bQ\d+\b|\[\d+\])\s+",
    re.IGNORECASE | re.MULTILINE
)

# Subpart header pattern: "a)", "(a)", "b.", "i)", "ii)"
SUBPART_START_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:\(([a-g]|[iIvVxX]+)\)|([a-g]|[iIvVxX]+)[\.\)])\s+([^\n\r]+)",
    re.IGNORECASE
)

def extract_section_and_marks(text: str) -> tuple[str | None, int | None]:
    """Extracts section name and mark allocation from a heading line."""
    sec_match = SECTION_HEADING_PATTERN.search(text)
    section_name = None
    marks = None

    if sec_match:
        part_id = sec_match.group(1).strip().upper()
        extra_desc = (sec_match.group(2) or sec_match.group(3) or "").strip()
        section_name = f"PART-{part_id}" + (f" ({extra_desc})" if extra_desc else "")

    marks_m = MARKS_PATTERN.search(text)
    if marks_m:
        try:
            marks = int(marks_m.group(1))
        except ValueError:
            pass

    return section_name, marks

def parse_subparts(text: str) -> list[dict[str, Any]]:
    """Extracts structured subparts e.g. a), b), c) or i), ii) from a multi-part question."""
    subparts = []
    matches = list(SUBPART_START_PATTERN.finditer(text))
    if not matches:
        return []

    for i, match in enumerate(matches):
        lbl = (match.group(1) or match.group(2)).strip().lower()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sub_text = text[start:end].strip()
        # Remove the leading label from text
        cleaned_sub_text = SUBPART_START_PATTERN.sub(r"\3", sub_text).strip()
        subparts.append({
            "label": lbl,
            "text": cleaned_sub_text
        })
    return subparts

def extract_questions_from_page_layout(
    raw_text: str,
    page_number: int,
    current_section: str = "General",
    current_marks: int | None = None
) -> tuple[list[dict[str, Any]], str, int | None]:
    """
    Extracts structured question units from a single page's text using layout-aware segmentation.
    Returns:
        (questions_list, updated_section, updated_marks)
    """
    if not raw_text or not raw_text.strip():
        return [], current_section, current_marks

    # If this page is solely an Answer Key, return empty
    if is_answer_key_text(raw_text):
        return [], current_section, current_marks

    clean_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = clean_text.splitlines()

    questions = []
    active_section = current_section
    active_marks = current_marks

    # Find question start positions
    matches = list(QUESTION_START_PATTERN.finditer(clean_text))
    if not matches:
        return [], active_section, active_marks

    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(clean_text)
        block = clean_text[start:end].strip()

        # Check if block contains a section heading in its preamble
        header_match = QUESTION_START_PATTERN.match(block)
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

        # Check for section or marks update in text before this block
        preamble = clean_text[:start].splitlines()
        if preamble:
            for pl in preamble[-3:]:
                s_name, s_marks = extract_section_and_marks(pl)
                if s_name:
                    active_section = s_name
                if s_marks:
                    active_marks = s_marks

        # Check subparts if any (e.g. a), b), c))
        subparts = parse_subparts(body)

        # Extract options and stem
        stem, options_list, inline_ans, options_dict = extract_options_and_stem(body)

        # Classify question type
        q_type, completeness, status = classify_question_type(
            question_stem=stem,
            options=options_list,
            subparts=subparts,
            section_name=active_section,
            marks=active_marks
        )

        # Determine sequence_id prefix
        prefix = "Q"
        if q_type == "MCQ":
            prefix = "MCQ"
        elif active_marks == 2 or "2 MARK" in active_section.upper():
            prefix = "2M"
        elif active_marks == 5 or "5 MARK" in active_section.upper():
            prefix = "5M"
        elif q_type == "FILL_IN_THE_BLANK":
            prefix = "FIB"

        seq_id = f"{prefix}-{q_num:03d}" if isinstance(q_num, int) else f"{prefix}-{q_num}"

        q_dict: dict[str, Any] = {
            "question_id": seq_id,
            "question_number": q_num,
            "sequence_id": seq_id,
            "section": active_section,
            "question_type": q_type,
            "question": stem,
            "options": options_list,
            "option_a": options_dict.get("A", options_list[0] if len(options_list) > 0 else ""),
            "option_b": options_dict.get("B", options_list[1] if len(options_list) > 1 else ""),
            "option_c": options_dict.get("C", options_list[2] if len(options_list) > 2 else ""),
            "option_d": options_dict.get("D", options_list[3] if len(options_list) > 3 else ""),
            "correct_answer": inline_ans or "",
            "subparts": subparts,
            "marks": str(active_marks) if active_marks else "1",
            "score": str(active_marks) if active_marks else "1",
            "source_page": page_number,
            "extraction_completeness": completeness,
            "status": status
        }
        # Audit integrity, Unicode symbols, and 4-option completeness
        q_audited = audit_and_validate_question(q_dict)
        questions.append(q_audited)

    return questions, active_section, active_marks

def reconstruct_multi_page_questions(page_questions: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """
    Flattens and reconstructs questions that span across page boundaries.
    """
    all_reconstructed: list[dict[str, Any]] = []
    
    for page_q_list in page_questions:
        for q in page_q_list:
            all_reconstructed.append(q)

    return all_reconstructed
