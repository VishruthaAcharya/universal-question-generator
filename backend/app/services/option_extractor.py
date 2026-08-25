import re
from typing import Any

# Pattern for option start delimiters
# Matches (a), (b), (c), (d), (A), (B), (C), (D), A., B., C., D., a), b), c), d), A), B), C), D), [A], [B], [a], [b], 1), 2), 3), 4)
OPTION_DELIM_PATTERN = re.compile(
    r"(?:^|(?<=\s)|(?<=[\n\r]))(?:\(([A-Da-d1-4])\)|([A-Da-d1-4])[\.\)](?!/)|\[([A-Da-d1-4])\])\s+",
    re.MULTILINE
)

# Inline same-line horizontal option splitter pattern: "(a) opt1 (b) opt2 (c) opt3 (d) opt4"
HORIZONTAL_OPTIONS_PATTERN = re.compile(
    r"(?:\(([a-dA-D1-4])\)|(?<=\s)([a-dA-D1-4])[\.\)])\s+([^\(\n\r]+?)(?=(?:\s*\([a-dA-D1-4]\)|\s+[a-dA-D1-4][\.\)]|$))",
    re.MULTILINE
)

# Inline answer patterns: "Ans: (b)", "Answer: B", "Correct Option: C", "Key: A"
INLINE_ANSWER_PATTERN = re.compile(
    r"(?:(?:Correct\s+)?Answer|Ans|Correct\s+Option|Key)\s*[\:\-\.]*\s*(?:Option\s*)?\(?([A-Da-d1-4]|True|False|[^\n\r]+?)\)?(?:\s*$|\s+(?=(?:Topic|Difficulty|Explanation|Bloom|Mark)))",
    re.IGNORECASE | re.MULTILINE
)

from app.services.symbol_normalizer import normalize_math_and_greek_symbols

def extract_options_and_stem(text: str) -> tuple[str, list[str], str | None, dict[str, str]]:
    """
    Extracts question stem, normalized list of options [optA, optB, optC, optD],
    inline correct answer (if present), and an options dictionary {'A': ..., 'B': ...}.
    Supports:
    - Same-line horizontal options: (a) text (b) text (c) text (d) text
    - Multiline vertical options:
      (a) text line 1
          wrapped line 2
      (b) text...
    - Mixed punctuation: A., (a), a), [A]
    """
    if not text or not text.strip():
        return "", [], None, {}

    clean_text = text.replace("\r\n", "\n").replace("\r", "\n").strip()

    # 1. Extract inline answer if present
    inline_ans = None
    ans_match = INLINE_ANSWER_PATTERN.search(clean_text)
    if ans_match:
        inline_ans = normalize_math_and_greek_symbols(ans_match.group(1).strip())
        # Remove answer line from text for option parsing
        text_before_ans = clean_text[:ans_match.start()].strip()
    else:
        text_before_ans = clean_text

    # 2. Try Horizontal Regex Split
    # Find all option delimiter positions
    matches = list(OPTION_DELIM_PATTERN.finditer(text_before_ans))
    
    if matches and len(matches) >= 2:
        # First match defines end of question stem
        stem = normalize_math_and_greek_symbols(text_before_ans[:matches[0].start()].strip())
        options_list = []
        options_dict = {}

        for i, match in enumerate(matches):
            label = match.group(1) or match.group(2) or match.group(3) or chr(65 + i)
            label_norm = label.upper()
            if label_norm.isdigit():
                idx_num = int(label_norm) - 1
                if 0 <= idx_num < 4:
                    label_norm = chr(65 + idx_num)

            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text_before_ans)
            opt_body = text_before_ans[start:end].strip()

            # Clean any trailing answer marker in option body
            opt_body = INLINE_ANSWER_PATTERN.sub("", opt_body).strip()
            opt_body_norm = normalize_math_and_greek_symbols(opt_body)
            if opt_body_norm:
                options_list.append(opt_body_norm)
                options_dict[label_norm] = opt_body_norm

        if len(options_list) >= 2:
            return stem, options_list, inline_ans, options_dict

    # 3. Fallback: Line-by-Line Option Extraction
    lines = text_before_ans.splitlines()
    stem_lines = []
    options_list = []
    options_dict = {}
    in_options = False
    current_label = None

    line_opt_pat = re.compile(r"^\s*(?:\(([A-Da-d1-4])\)|([A-Da-d1-4])[\.\)\:\-]|\b([A-Da-d1-4])\b\s*[\:\-])\s*(.*)$")

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            continue

        m = line_opt_pat.match(trimmed)
        if m:
            in_options = True
            raw_label = m.group(1) or m.group(2) or m.group(3)
            current_label = raw_label.upper() if raw_label else chr(65 + len(options_list))
            if current_label.isdigit():
                idx_num = int(current_label) - 1
                if 0 <= idx_num < 4:
                    current_label = chr(65 + idx_num)

            opt_content = m.group(4).strip()
            # Check if this line also contains subsequent options on same line (e.g. "(a) opt1 (b) opt2")
            sub_matches = list(OPTION_DELIM_PATTERN.finditer(opt_content))
            if sub_matches:
                # Split multiple options on the same line
                opt_1 = normalize_math_and_greek_symbols(opt_content[:sub_matches[0].start()].strip())
                options_list.append(opt_1)
                options_dict[current_label] = opt_1
                for si, s_match in enumerate(sub_matches):
                    s_lbl = (s_match.group(1) or s_match.group(2) or s_match.group(3) or "B").upper()
                    s_start = s_match.end()
                    s_end = sub_matches[si + 1].start() if si + 1 < len(sub_matches) else len(opt_content)
                    s_text = normalize_math_and_greek_symbols(opt_content[s_start:s_end].strip())
                    if s_text:
                        options_list.append(s_text)
                        options_dict[s_lbl] = s_text
            else:
                opt_val = normalize_math_and_greek_symbols(opt_content)
                options_list.append(opt_val)
                options_dict[current_label] = opt_val
        elif in_options:
            # Multi-line continuation of current option
            if options_list:
                cleaned_tail = normalize_math_and_greek_symbols(trimmed)
                options_list[-1] += " " + cleaned_tail
                if current_label and current_label in options_dict:
                    options_dict[current_label] += " " + cleaned_tail
        else:
            stem_lines.append(trimmed)

    if len(options_list) >= 2:
        stem_norm = normalize_math_and_greek_symbols(" ".join(stem_lines).strip())
        return stem_norm, options_list, inline_ans, options_dict

    clean_norm = normalize_math_and_greek_symbols(clean_text)
    return clean_norm, [], inline_ans, {}
