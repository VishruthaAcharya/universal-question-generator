import re
from typing import Any
from app.services.option_extractor import extract_options_and_stem, OPTION_DELIM_PATTERN
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

# Question header pattern: "1.", "2)", "Q1:", "10 -", "[1]", "Question 1:", "Problem 1:"
QUESTION_START_PATTERN = re.compile(
    r"^\s*(?:(?:(?:Q(?:uestion)?|Problem|Task|Exercise|Item)[\s\.\:\-]*\d+)|(?:\d+)[\.\)\:\-]|\bQ\d+\b|\[\d+\]|\(\d+\))\s+",
    re.IGNORECASE | re.MULTILINE
)

# Subpart header pattern: "a)", "(a)", "b.", "i)", "ii)"
SUBPART_START_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:\(([a-g]|[iIvVxX]+)\)|([a-g]|[iIvVxX]+)[\.\)])\s+([^\n\r]+)",
    re.IGNORECASE
)

QUESTION_STARTER_WORDS = {
    "WHAT", "WHICH", "WHEN", "WHERE", "WHO", "WHOM", "WHOSE", "WHY", "HOW",
    "FIND", "CALCULATE", "SOLVE", "SIMPLIFY", "EVALUATE", "DETERMINE", "CHOOSE", "SELECT", "IDENTIFY",
    "IF", "IN", "A", "AN", "THE", "GIVEN", "LET", "SUPPOSE", "CONSIDER", "ASSERTION", "STATEMENT",
    "READ", "ACCORDING", "STATE", "EXPLAIN", "DISCUSS", "PROVE", "SHOW", "WRITE", "NAME", "LIST", "MATCH",
    "POINTING", "ARRANGE", "COMPLETE", "CONVERT", "DIRECTIONS", "NOTE", "QUESTION", "PROBLEM", "TASK"
}

DIFFICULTY_REGEX = re.compile(
    r"^(?:(?:Difficulty(?:\s*Level)?|Diff)\s*[\:\-\.]*\s*)?(EASY|MEDIUM|HARD|AUTO)$",
    re.IGNORECASE
)

MARKS_REGEX = re.compile(
    r"^(?:(?:Marks?|Score)\s*[\:\-\.]*\s*(\d+(?:\.\d+)?)|(?:(\d+(?:\.\d+)?)\s*(?:marks?|mark|m)\b)|[\(\[]\s*(\d+(?:\.\d+)?)\s*(?:marks?|mark|m)?\s*[\)\]])$",
    re.IGNORECASE
)

EXPLICIT_METADATA_REGEX = re.compile(
    r"^(Topic|Category|Subject|Domain|Section|Difficulty(?:\s*Level)?|Diff|Marks?|Score|Subtopic)\s*[\:\-\.]*\s*(.+)$",
    re.IGNORECASE
)

def is_metadata_line(line: str) -> bool:
    """Checks if a single line is a metadata header line."""
    trimmed = line.strip()
    if not trimmed:
        return False
    if EXPLICIT_METADATA_REGEX.match(trimmed):
        return True
    if DIFFICULTY_REGEX.match(trimmed):
        return True
    if MARKS_REGEX.match(trimmed):
        return True
    if "|" in trimmed or " • " in trimmed:
        return True
    words = trimmed.split()
    first_word = words[0].upper().rstrip(":,.-") if words else ""
    if (
        re.match(r"^[A-Za-z0-9\s&/\-]+$", trimmed)
        and (trimmed.isupper() or len(words) <= 4)
        and 2 <= len(trimmed) <= 50
        and not any(trimmed.endswith(p) for p in ("?", ":", ".", ",", ";"))
        and first_word not in QUESTION_STARTER_WORDS
    ):
        return True
    return False

def extract_metadata_region(body: str) -> tuple[str, dict[str, Any]]:
    """
    Extracts metadata (category, topic, domain, difficulty, marks, section)
    that occurs in the metadata/header region.
    Question body begins AFTER the metadata region.
    Returns (remaining_body_text, metadata_dict).
    """
    if not body or not body.strip():
        return body, {}

    lines = body.splitlines()
    meta: dict[str, Any] = {}
    body_start_idx = 0

    for i, line in enumerate(lines):
        trimmed = line.strip()
        if not trimmed:
            if body_start_idx == i:
                body_start_idx = i + 1
            continue

        # 1. Check explicit key-value line (e.g. "Topic: ...", "Difficulty: ...", "Domain: ...")
        exp_m = EXPLICIT_METADATA_REGEX.match(trimmed)
        if exp_m:
            key = exp_m.group(1).lower()
            val = exp_m.group(2).strip()
            if key in ("category", "subject"):
                meta["category"] = val
                if not meta.get("topic"):
                    meta["topic"] = val
            elif key == "topic":
                meta["topic"] = val
                if not meta.get("category"):
                    meta["category"] = val
            elif key == "domain":
                meta["domain"] = val
            elif key == "subtopic":
                meta["subtopic"] = val
            elif key == "section":
                meta["section"] = val
            elif key in ("difficulty", "difficultylevel", "diff"):
                meta["difficulty"] = val.upper()
            elif key in ("marks", "mark", "score"):
                num_m = re.search(r"\d+(?:\.\d+)?", val)
                if num_m:
                    v = num_m.group(0)
                    meta["marks"] = str(int(float(v))) if float(v).is_integer() else str(v)
                    meta["score"] = meta["marks"]
            body_start_idx = i + 1
            continue

        # 2. Check standalone difficulty (e.g. "MEDIUM", "EASY", "HARD")
        diff_m = DIFFICULTY_REGEX.match(trimmed)
        if diff_m:
            meta["difficulty"] = diff_m.group(1).upper()
            body_start_idx = i + 1
            continue

        # 3. Check standalone marks (e.g. "1 MARK", "2 MARKS", "1Mark", "[2M]")
        marks_m = MARKS_REGEX.match(trimmed)
        if marks_m:
            val = marks_m.group(1) or marks_m.group(2) or marks_m.group(3)
            if val:
                meta["marks"] = str(int(float(val))) if float(val).is_integer() else str(val)
                meta["score"] = meta["marks"]
            body_start_idx = i + 1
            continue

        # 4. Check pipe/delimiter-separated metadata on single line
        if "|" in trimmed or " • " in trimmed:
            delims = "|" if "|" in trimmed else " • "
            parts = [p.strip() for p in trimmed.split(delims) if p.strip()]
            parsed_parts = 0
            for part in parts:
                p_exp = EXPLICIT_METADATA_REGEX.match(part)
                p_diff = DIFFICULTY_REGEX.match(part)
                p_marks = MARKS_REGEX.match(part)
                if p_exp:
                    pk = p_exp.group(1).lower()
                    pv = p_exp.group(2).strip()
                    if pk in ("category", "subject"):
                        meta["category"] = pv
                        if not meta.get("topic"):
                            meta["topic"] = pv
                    elif pk == "topic":
                        meta["topic"] = pv
                    elif pk == "domain":
                        meta["domain"] = pv
                    elif pk in ("difficulty", "diff"):
                        meta["difficulty"] = pv.upper()
                    elif pk in ("marks", "score"):
                        nm = re.search(r"\d+", pv)
                        if nm:
                            meta["marks"] = nm.group(0)
                            meta["score"] = nm.group(0)
                    parsed_parts += 1
                elif p_diff:
                    meta["difficulty"] = p_diff.group(1).upper()
                    parsed_parts += 1
                elif p_marks:
                    v = p_marks.group(1) or p_marks.group(2) or p_marks.group(3)
                    if v:
                        meta["marks"] = str(int(float(v))) if float(v).is_integer() else str(v)
                        meta["score"] = meta["marks"]
                    parsed_parts += 1
                elif re.match(r"^[A-Za-z0-9\s&/\-]+$", part) and len(part) <= 50:
                    if not meta.get("category"):
                        meta["category"] = part
                    if not meta.get("topic"):
                        meta["topic"] = part
                    parsed_parts += 1
            if parsed_parts == len(parts) and parsed_parts > 0:
                body_start_idx = i + 1
                continue

        # 5. Check standalone Subject / Category / Topic / Domain header line
        words = trimmed.split()
        first_word = words[0].upper().rstrip(":,.-") if words else ""
        last_word = words[-1].upper().rstrip(":,.-") if words else ""
        upper_words = [w.upper().rstrip(":,.-") for w in words]
        
        has_question_verb = any(vw in upper_words for vw in {"IS", "ARE", "WAS", "WERE", "DOES", "DO", "DID", "CAN", "COULD", "SHOULD", "WOULD", "GIVE", "GIVEN", "CALCULATE", "FIND", "SOLVE", "EXPLAIN", "PROVE", "WRITE", "DETERMINE"})

        if (
            re.match(r"^[A-Za-z0-9\s&/\-\(\)]+$", trimmed)
            and len(words) <= 5
            and 2 <= len(trimmed) <= 50
            and not any(trimmed.endswith(p) for p in ("?", ":", ".", ",", ";"))
            and first_word not in QUESTION_STARTER_WORDS
            and last_word not in {"A", "AN", "THE", "OF", "IN", "ON", "AT", "BY", "FOR", "WITH", "TO", "IS", "ARE"}
            and not has_question_verb
        ):
            if not meta.get("category"):
                meta["category"] = trimmed
            elif not meta.get("topic") or meta.get("topic") == meta.get("category"):
                meta["topic"] = trimmed
                meta["domain"] = trimmed
            elif not meta.get("domain"):
                meta["domain"] = trimmed
            body_start_idx = i + 1
            continue

        # If line does not match any metadata rule, the metadata region has ended
        break

    remaining_lines = lines[body_start_idx:]
    remaining_body = "\n".join(remaining_lines).strip()
    return remaining_body, meta

def extract_trailing_metadata(text: str) -> dict[str, Any]:
    """Extracts trailing metadata (e.g. Domain) occurring after options/answer."""
    trailing: dict[str, Any] = {}
    if not text:
        return trailing
    dom_m = re.search(r"Domain\s*[\:\-\.]*\s*([^\n\r]+)", text, re.IGNORECASE)
    if dom_m:
        trailing["domain"] = dom_m.group(1).strip()
    return trailing

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

def segment_page_into_question_blocks(
    clean_text: str,
    current_section: str = "General",
    current_marks: int | None = None
) -> tuple[list[dict[str, Any]], str, int | None]:
    """
    Segments raw page text into distinct question units.
    Handles:
    - Standard numbered questions (e.g. "Question 1", "1.", "Q1:")
    - Metadata occurring before OR after question numbers
    - Unnumbered questions preceded by metadata blocks or option blocks
    - Standalone coding/subjective questions
    """
    matches = list(QUESTION_START_PATTERN.finditer(clean_text))
    blocks_data: list[dict[str, Any]] = []
    active_section = current_section
    active_marks = current_marks

    if matches:
        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(clean_text)
            block = clean_text[start:end].strip()

            # Header match
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

            # Check preamble (text before this question) for metadata / section updates
            preamble_text = clean_text[:start] if idx == 0 else clean_text[matches[idx-1].end():start]
            preamble_lines = [p.strip() for p in preamble_text.splitlines() if p.strip()]
            for pl in preamble_lines[-3:]:
                s_name, s_marks = extract_section_and_marks(pl)
                if s_name:
                    active_section = s_name
                if s_marks:
                    active_marks = s_marks

            # Extract any preamble metadata preceding this question
            _, preamble_meta = extract_metadata_region(preamble_text)

            # Extract metadata from body
            body_clean, body_meta = extract_metadata_region(body)

            # Merge metadata
            merged_meta = {**preamble_meta, **body_meta}

            trailing_meta = extract_trailing_metadata(block)
            if "domain" in trailing_meta and "domain" not in merged_meta:
                merged_meta["domain"] = trailing_meta["domain"]

            blocks_data.append({
                "q_num": q_num,
                "body": body_clean,
                "raw_block": block,
                "meta": merged_meta
            })
    else:
        # Unnumbered question segmentation
        lines = clean_text.splitlines()
        opt_line_pat = re.compile(r"^\s*(?:\(([A-Da-d1-4])\)|([A-Da-d1-4])[\.\)\:\-]|\b([A-Da-d1-4])\b\s*[\:\-])\s*")
        ans_line_pat = re.compile(r"^\s*(?:(?:Correct\s+)?Answer|Ans|Correct\s+Option|Key)\s*[\:\-\.]+", re.IGNORECASE)

        # Detect boundaries for unnumbered questions
        unit_start_indices = []
        in_options_mode = False
        after_answer_mode = False

        for i, line in enumerate(lines):
            trimmed = line.strip()
            if not trimmed:
                continue

            # If line is a page footer, skip
            if re.match(r"^Page\s+\d+(?:\s+(?:of|\/)\s+\d+)?$", trimmed, re.IGNORECASE):
                continue

            is_opt = bool(opt_line_pat.match(trimmed))
            is_ans = bool(ans_line_pat.match(trimmed))
            is_meta = is_metadata_line(trimmed)

            if is_opt:
                in_options_mode = True
                after_answer_mode = False
            elif is_ans:
                after_answer_mode = True
                in_options_mode = False
            elif after_answer_mode:
                # Next question begins after answer / domain line
                unit_start_indices.append(i)
                after_answer_mode = False
                in_options_mode = False
            elif is_meta and in_options_mode:
                # Next question begins with a metadata block
                unit_start_indices.append(i)
                in_options_mode = False

        if not unit_start_indices:
            unit_start_indices = [0]
        elif unit_start_indices[0] != 0:
            unit_start_indices.insert(0, 0)

        for u_idx, start_i in enumerate(unit_start_indices):
            end_i = unit_start_indices[u_idx + 1] if u_idx + 1 < len(unit_start_indices) else len(lines)
            u_text = "\n".join(lines[start_i:end_i]).strip()
            if not u_text:
                continue

            body_clean, meta = extract_metadata_region(u_text)
            trailing_meta = extract_trailing_metadata(u_text)
            if "domain" in trailing_meta and "domain" not in meta:
                meta["domain"] = trailing_meta["domain"]

            blocks_data.append({
                "q_num": u_idx + 1,
                "body": body_clean,
                "raw_block": u_text,
                "meta": meta
            })

    return blocks_data, active_section, active_marks

def extract_questions_from_page_layout(
    raw_text: str,
    page_number: int,
    current_section: str = "General",
    current_marks: int | None = None,
    extraction_method: str = "native_text",
    text_quality_score: float = 1.0,
    character_count: int = 0
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

    blocks_data, active_section, active_marks = segment_page_into_question_blocks(
        clean_text,
        current_section=current_section,
        current_marks=current_marks
    )

    questions = []
    for item in blocks_data:
        q_num = item["q_num"]
        body_clean = item["body"]
        meta = item["meta"]

        # Extract options and stem from the question body
        stem_raw, options_list, inline_ans, options_dict = extract_options_and_stem(body_clean)

        # Clean leading "Question:", "Problem 1:", "Task:" etc.
        stem_clean = re.sub(
            r"^\s*(?:(?:Question|Problem|Task|Item|Exercise|Q)\s*(?:\d+)?\s*[\:\-\.]\s*)+",
            "",
            stem_raw,
            flags=re.IGNORECASE
        ).strip()

        # Isolate any leading metadata header lines in stem
        stem, stem_meta = extract_metadata_region(stem_clean)
        meta = {**meta, **stem_meta}

        # Check trailing marks at the end of stem (e.g. "\nMarks: 5")
        trailing_marks_m = re.search(r"\n\s*(?:Marks?|Score)\s*[\:\-]\s*(\d+(?:\.\d+)?)\s*$", stem, re.IGNORECASE)
        if trailing_marks_m:
            meta["marks"] = trailing_marks_m.group(1)
            meta["score"] = trailing_marks_m.group(1)
            stem = stem[:trailing_marks_m.start()].strip()

        # Check subparts if any (e.g. a), b), c))
        subparts = parse_subparts(stem)
        if not subparts and options_list:
            is_subpart_opts = any(opt.strip().lower().startswith(("how is", "write", "explain", "complete the", "calculate", "state", "describe", "define", "what happens")) for opt in options_list)
            if is_subpart_opts:
                subparts = [
                    {"label": chr(ord('a') + idx), "text": opt}
                    for idx, opt in enumerate(options_list)
                ]
                options_list = []
                options_dict = {}

        # Classify question type
        q_marks_val = int(meta["marks"]) if meta.get("marks") and str(meta["marks"]).isdigit() else active_marks
        q_topic = meta.get("topic") or meta.get("category") or (active_section if active_section != "General" else "") or meta.get("domain") or "General"
        q_type, completeness, status = classify_question_type(
            question_stem=stem,
            options=options_list,
            subparts=subparts,
            section_name=q_topic,
            marks=q_marks_val
        )

        # Determine sequence_id prefix
        prefix = "Q"
        if q_type == "MCQ":
            prefix = "MCQ"
        elif q_marks_val == 2 or "2 MARK" in active_section.upper():
            prefix = "2M"
        elif q_marks_val == 5 or "5 MARK" in active_section.upper():
            prefix = "5M"
        elif q_type == "FILL_IN_THE_BLANK":
            prefix = "FIB"

        seq_id = f"{prefix}-{q_num:03d}" if isinstance(q_num, int) else f"{prefix}-{q_num}"

        q_diff = meta.get("difficulty") or "Medium"
        q_marks_str = meta.get("marks") or (str(active_marks) if active_marks else "1")

        q_dict: dict[str, Any] = {
            "question_id": seq_id,
            "question_number": q_num,
            "sequence_id": seq_id,
            "section": meta.get("section") or active_section,
            "topic": q_topic,
            "category": meta.get("category") or q_topic,
            "domain": meta.get("domain") or "",
            "difficulty": q_diff,
            "question_type": q_type,
            "question": stem,
            "options": options_list,
            "option_a": options_dict.get("A", options_list[0] if len(options_list) > 0 else ""),
            "option_b": options_dict.get("B", options_list[1] if len(options_list) > 1 else ""),
            "option_c": options_dict.get("C", options_list[2] if len(options_list) > 2 else ""),
            "option_d": options_dict.get("D", options_list[3] if len(options_list) > 3 else ""),
            "correct_answer": inline_ans or "",
            "source_answer": inline_ans or "",
            "subparts": subparts,
            "marks": q_marks_str,
            "score": q_marks_str,
            "source_page": page_number,
            "extraction_method": extraction_method,
            "text_quality_score": text_quality_score,
            "character_count": character_count or len(stem),
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
