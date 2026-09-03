import re
from typing import Any

# Headings that strongly identify an Answer Key section or page
ANSWER_KEY_HEADING_PATTERNS = [
    re.compile(r"^\s*(?:#+\s*)?(?:answers?\s*keys?|solutions?\s*keys?|correct\s*answers?|answer\s*sheet|solutions?|correct\s*options?|key\s*answers?|answers?\s*to\s*questions?|key\s*to\s*assessment|answers?\s*(?:key)?\s*(?:&|and)\s*solutions?|answers?)\s*[:\-]*\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*SECTION\s*[A-Z0-9]*\s*[\:\-]\s*(?:ANSWER\s*KEY|SOLUTIONS|ANSWERS)\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*(?:CHAPTER|UNIT|IMAGE|FILE|PAGE|TEST|SET|PAPER|GROUP)\s*\d+\s*[\:\-]\s*(?:ANSWER\s*KEY|ANSWERS|SOLUTIONS)\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*(?:IMAGE|FILE|PAGE|TEST|SET|PAPER|GROUP|CHAPTER|UNIT|SECTION|PART)\s*[A-Za-z0-9IVXLCDM\.\-_\s]+(?:\s*[\:\-]\s*(?:ANSWER\s*KEY|ANSWERS|SOLUTIONS)?)?\s*$", re.IGNORECASE | re.MULTILINE),
]

# Patterns for discrete answer key entries
# 1. "1. B", "1) B", "1 - B", "1: B", "1. (B)", "1.(B)", "[1] B", "1 B", "(4) D", "[3] B"
DISCRETE_ENTRY_PATTERN = re.compile(
    r"(?:^|[\n\r,;\t]|(?<=\s))(?:[\[\(]?\s*(?:Q(?:uestion)?[\s\.\:\-]*)?(\d+|[A-Za-z]\d+)\s*[\.\)\:\-\]]*)\s*[\:\-\=\s]*\(?([A-Da-d1-4]|True|False|[A-Za-z0-9\.\-\+\s]{1,40}?)\)?(?=(?:[\n\r,;\t\)]|\s+(?:[\[\(]?\d+[\.\)\:\-]|\bQ\d+)|$))",
    re.MULTILINE
)

# Alternative compact pattern: "1-A, 2-B, 3-C, 4-D" or "1:A 2:B 3:C"
COMPACT_ENTRY_PATTERN = re.compile(
    r"\b(\d+)\s*[\:\-\.]\s*([A-Da-d1-4])\b"
)

# Range grouped pattern: "1-10: A B C D A B C D A B" or "1-5: A, B, C, D, A" or "1 - 5 : B D A C A"
RANGE_GROUPED_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:Q(?:uestion)?s?[\s\.]*)?(\d+)\s*[\-\–\—\to]+\s*(\d+)\s*[\:\-\=]\s*([A-Da-d1-4\s\,\;]+)(?=\n|$)",
    re.IGNORECASE | re.MULTILINE
)

# Chapter or section header pattern
CHAPTER_HEADER_PATTERN = re.compile(
    r"^\s*(?:CHAPTER|UNIT|SECTION|PART|IMAGE|FILE|PAGE|TEST|SET|PAPER|GROUP)\s*([A-Za-z0-9IVXLCDM\.\-_\s]+)(?:[\:\-\.]\s*(.*))?$",
    re.IGNORECASE | re.MULTILINE
)

def is_answer_key_text(text: str) -> bool:
    """
    Determines if a page or text block is primarily an Answer Key section rather than question content.
    """
    if not text or not text.strip():
        return False

    clean_text = text.strip()
    lines = [l.strip() for l in clean_text.splitlines() if l.strip()]
    if not lines:
        return False

    # 1. Check explicit heading in top 5 lines
    has_explicit_heading = False
    for line in lines[:5]:
        for pat in ANSWER_KEY_HEADING_PATTERNS:
            if pat.search(line):
                has_explicit_heading = True
                break
        if has_explicit_heading:
            break

    # 2. Check density of answer key entries vs full question sentences
    compact_matches = list(COMPACT_ENTRY_PATTERN.finditer(clean_text))
    discrete_matches = list(DISCRETE_ENTRY_PATTERN.finditer(clean_text))
    range_matches = list(RANGE_GROUPED_PATTERN.finditer(clean_text))

    total_key_entries = max(len(compact_matches), len(discrete_matches))
    if range_matches:
        for rm in range_matches:
            try:
                start_n = int(rm.group(1))
                end_n = int(rm.group(2))
                total_key_entries += max(1, (end_n - start_n + 1))
            except Exception:
                total_key_entries += 5

    question_indicators = len(re.findall(r"\?|which of the following|what is the|calculate|find the|explain", clean_text, re.IGNORECASE))

    opt_lines_count = len(re.findall(r"^\s*(?:\([A-Da-d1-4]\)|[A-Da-d1-4][\.\)])\s+", clean_text, re.MULTILINE))
    if opt_lines_count >= 3 and not has_explicit_heading:
        return False

    if has_explicit_heading:
        return True

    if total_key_entries >= 4 and question_indicators <= 1:
        avg_line_len = sum(len(l) for l in lines) / len(lines)
        if avg_line_len < 40 or total_key_entries >= len(lines) * 0.4:
            return True

    return False

def extract_answer_key_entries(
    text: str,
    page_number: int,
    section_name: str = "Answer Key",
    chapter_name: str | None = None
) -> list[dict[str, Any]]:
    """
    Extracts and normalizes discrete answer key records from text.
    Handles multiple formats:
    - 1. A, 2. B, 3. C
    - Q1 - A, Q2 - B
    - Q1 = 60 km/h, Q2 = 180
    - 1-A, 2-B, 3-C
    - 1) A, 2) B
    - 1-10: A B C D A B C D A B
    - Table format: 1 | A
    """
    if not text or not text.strip():
        return []

    clean_text = text.replace("\r\n", "\n").replace("\r", "\n")
    entries: list[dict[str, Any]] = []
    seen_q_nums = set()

    current_chapter = chapter_name
    current_section = section_name

    lines = clean_text.splitlines()
    
    # 1. First check Range Grouped pattern e.g. "1-10: A B C D A B C D A B"
    for r_match in RANGE_GROUPED_PATTERN.finditer(clean_text):
        try:
            start_num = int(r_match.group(1))
            end_num = int(r_match.group(2))
            raw_tokens = r_match.group(3).strip()
            ans_tokens = [t.strip().upper() for t in re.split(r"[\s\,\;]+", raw_tokens) if t.strip()]
            
            for idx, q_num in enumerate(range(start_num, end_num + 1)):
                if idx < len(ans_tokens):
                    ans_letter = ans_tokens[idx]
                    if len(ans_letter) == 1 and ans_letter in "ABCD1234":
                        entries.append({
                            "question_number": q_num,
                            "answer": ans_letter,
                            "source_page": page_number,
                            "source_section": current_section,
                            "source_chapter": current_chapter,
                            "answer_key_group": current_chapter or current_section,
                            "source_type": "EXPLICIT_ANSWER_KEY",
                            "raw_text": f"{q_num}: {ans_letter}"
                        })
                        seen_q_nums.add((q_num, current_chapter))
        except Exception:
            pass

    # 2. Check line by line to capture chapter updates and entries
    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            continue

        # Check chapter / image header e.g. "IMAGE 1", "IMAGE 2", "CHAPTER 1", "SECTION A"
        chap_m = CHAPTER_HEADER_PATTERN.match(trimmed)
        if chap_m:
            current_chapter = chap_m.group(0).strip()
            current_section = chap_m.group(0).strip()
            continue

        # Check section header
        if any(pat.match(trimmed) for pat in ANSWER_KEY_HEADING_PATTERNS):
            current_section = trimmed
            continue

        # Check compact format on single line "1-A, 2-C, 3-B" or "1.A 2.B 3.C"
        compact_matches = list(COMPACT_ENTRY_PATTERN.finditer(trimmed))
        if len(compact_matches) >= 2:
            for cm in compact_matches:
                try:
                    q_num = int(cm.group(1))
                    ans_val = cm.group(2).strip().upper()
                    entry_key = (q_num, current_chapter)
                    if entry_key not in seen_q_nums:
                        entries.append({
                            "question_number": q_num,
                            "answer": ans_val,
                            "source_page": page_number,
                            "source_section": current_section,
                            "source_chapter": current_chapter,
                            "answer_key_group": current_chapter or current_section,
                            "source_type": "EXPLICIT_ANSWER_KEY",
                            "raw_text": cm.group(0)
                        })
                        seen_q_nums.add(entry_key)
                except Exception:
                    pass
            continue

        # Check single line key-value e.g. "Q1 = 60 km/h", "Q1: 60 km/h", "1. 60 km/h", "Q6 = All squares are rectangles."
        line_kv = re.match(r"^\s*(?:[\[\(]?\s*(?:Q(?:uestion)?[\s\.\:\-]*)?(\d+|[A-Za-z]\d+)\s*[\.\)\:\-\]]*)\s*[\:\-\=\s]\s*(.+)$", trimmed)
        if line_kv and not chap_m and not any(pat.match(trimmed) for pat in ANSWER_KEY_HEADING_PATTERNS):
            q_num_raw = line_kv.group(1).strip()
            ans_raw = line_kv.group(2).strip()
            if len(ans_raw) <= 80 and not any(ans_raw.lower().startswith(w) for w in ["what ", "which ", "how ", "why ", "calculate ", "find "]):
                try:
                    q_num = int(q_num_raw)
                except ValueError:
                    q_num = q_num_raw
                ans_clean = ans_raw.upper() if len(ans_raw) <= 2 and ans_raw.upper() in "ABCD" else ans_raw
                entry_key = (q_num, current_chapter)
                if entry_key not in seen_q_nums:
                    entries.append({
                        "question_number": q_num,
                        "answer": ans_clean,
                        "source_page": page_number,
                        "source_section": current_section,
                        "source_chapter": current_chapter,
                        "answer_key_group": current_chapter or current_section,
                        "source_type": "EXPLICIT_ANSWER_KEY",
                        "raw_text": trimmed
                    })
                    seen_q_nums.add(entry_key)
                continue

        # Check discrete single or multi entries on the line e.g. "1. B", "Q1 - D", "1) C"
        discrete_matches = list(DISCRETE_ENTRY_PATTERN.finditer(trimmed))
        for dm in discrete_matches:
            q_num_raw = dm.group(1).strip()
            ans_raw = dm.group(2).strip()

            if len(ans_raw) > 80:
                continue

            try:
                q_num = int(q_num_raw)
            except ValueError:
                q_num = q_num_raw

            ans_clean = ans_raw.upper() if len(ans_raw) <= 2 and ans_raw.upper() in "ABCD" else ans_raw
            entry_key = (q_num, current_chapter)
            if entry_key not in seen_q_nums:
                entries.append({
                    "question_number": q_num,
                    "answer": ans_clean,
                    "source_page": page_number,
                    "source_section": current_section,
                    "source_chapter": current_chapter,
                    "answer_key_group": current_chapter or current_section,
                    "source_type": "EXPLICIT_ANSWER_KEY",
                    "raw_text": dm.group(0)
                })
                seen_q_nums.add(entry_key)

    return entries
