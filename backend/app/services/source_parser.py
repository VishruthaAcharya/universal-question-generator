import time
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from app.config import settings
from app.services.source_reader import read_source_pages
from app.services.azure_openai import extract_questions_from_text, extract_questions_from_image
from app.services.deterministic_parser import extract_questions_from_dataframe
from app.services.layout_extractor import extract_questions_from_page_layout
from app.services.answer_key_detector import (
    is_answer_key_text,
    extract_answer_key_entries,
    ANSWER_KEY_HEADING_PATTERNS,
)
from app.services.cross_page_mapper import map_cross_page_answers
from app.services.cache_service import (
    compute_file_hash,
    get_cached_extraction,
    save_cached_extraction,
)

def compute_extraction_statistics(
    questions: list[dict[str, Any]],
    pages_count: int,
    elapsed_ms: float,
    visual_pages_count: int,
    pages_breakdown: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Computes dynamic extraction intelligence statistics across all questions."""
    total_q = len(questions)
    mcqs = sum(1 for q in questions if q.get("question_type") == "MCQ")
    fibs = sum(1 for q in questions if q.get("question_type") == "FILL_IN_THE_BLANK")
    short_ans = sum(1 for q in questions if q.get("question_type") in ["SHORT_ANSWER", "VERY_SHORT_ANSWER"])
    long_ans = sum(1 for q in questions if q.get("question_type") == "LONG_ANSWER")
    reaction_diag = sum(1 for q in questions if q.get("question_type") in ["REACTION_COMPLETION", "DIAGRAM_BASED", "IDENTIFY_COMPOUND"] or "reaction" in str(q.get("question", "")).lower())
    
    review_req = sum(1 for q in questions if q.get("status") in ["REVIEW_REQUIRED", "VISUAL_EXTRACTION_REQUIRED", "AMBIGUOUS_MAPPING"] or q.get("extraction_completeness", 1.0) < 0.70)
    
    confidences = [q.get("extraction_completeness", 0.95) for q in questions]
    avg_conf = sum(confidences) / len(confidences) if confidences else 1.0

    native_text_pages = sum(1 for p in (pages_breakdown or []) if p.get("extraction_method") == "native_text")
    ocr_pages = sum(1 for p in (pages_breakdown or []) if p.get("extraction_method") == "OCR")

    return {
        "pages_processed": pages_count,
        "total_questions_detected": total_q,
        "mcqs_detected": mcqs,
        "fill_in_the_blanks": fibs,
        "short_answer": short_ans,
        "long_answer": long_ans,
        "diagram_reaction_questions": reaction_diag,
        "questions_requiring_vision": visual_pages_count,
        "questions_requiring_review": review_req,
        "native_text_pages_count": native_text_pages,
        "ocr_pages_count": ocr_pages,
        "pages_breakdown": pages_breakdown or [],
        "average_extraction_confidence": round(avg_conf, 3),
        "extraction_time_ms": round(elapsed_ms, 1)
    }

def parse_source_document(path: str) -> list[dict[str, Any]]:
    """
    Layout-aware, multi-stage question extraction pipeline:
    1. Reads document pages preserving layout, text blocks, drawings, and images.
    2. Identifies and segregates Answer Key pages from Question Content pages.
    3. Performs deterministic layout-aware question segmentation (capturing sections, marks, subparts, options).
    4. Queues unstructured/scanned pages for Azure OpenAI Vision processing.
    5. Applies hierarchical cross-page Answer Key -> Question mapping.
    6. Attaches dynamic extraction statistics to output metadata.
    7. Caches verified extraction results.
    """
    start_time = time.perf_counter()

    # Step 1: Content Hash Caching
    file_hash = compute_file_hash(path)
    if settings.enable_extraction_cache:
        cached = get_cached_extraction(file_hash)
        if cached is not None:
            return cached

    pages = read_source_pages(path)
    all_questions: list[dict[str, Any]] = []
    all_answer_key_entries: list[dict[str, Any]] = []

    # State machine for section continuity across pages
    active_section = "General"
    active_marks = None

    # Track pages with visual drawings/images for targeted processing
    visual_pages_count = sum(1 for p in pages if p.get("has_visual", False))

    # Diagnostic page breakdown
    pages_breakdown = [
        {
            "page_number": p.get("page_number", idx + 1),
            "extraction_method": p.get("extraction_method", "native_text"),
            "text_quality_score": p.get("text_quality_score", 1.0),
            "character_count": p.get("character_count", len(str(p.get("content", "")))),
        }
        for idx, p in enumerate(pages)
    ]

    # Pages requiring AI fallback
    ai_tasks: list[tuple[int, dict[str, Any]]] = []

    for page_idx, page in enumerate(pages):
        page_num = page.get("page_number", page_idx + 1)
        page_type = page.get("type", "text")
        content = page.get("content")
        method = page.get("extraction_method", "native_text")
        q_score = page.get("text_quality_score", 1.0)
        char_count = page.get("character_count", 0)

        if page_type == "dataframe" and "df" in page:
            # Deterministic tabular extraction
            df_questions = extract_questions_from_dataframe(page["df"], page_num)
            if df_questions:
                for dq in df_questions:
                    dq.setdefault("extraction_method", "native_text")
                    dq.setdefault("text_quality_score", 1.0)
                    dq.setdefault("character_count", len(str(dq.get("question", ""))))
                all_questions.extend(df_questions)
            else:
                ai_tasks.append((page_idx, page))

        elif page_type == "text":
            text_str = str(content or "").strip()
            if not text_str:
                continue

            # Check if this page is purely an Answer Key page
            if is_answer_key_text(text_str):
                entries = extract_answer_key_entries(text_str, page_num)
                if entries:
                    all_answer_key_entries.extend(entries)
            else:
                # Check if there is an embedded Answer Key section in this page
                question_text = text_str
                for pat in ANSWER_KEY_HEADING_PATTERNS:
                    m = pat.search(text_str)
                    if m:
                        q_part = text_str[:m.start()].strip()
                        ans_part = text_str[m.start():].strip()
                        if q_part:
                            question_text = q_part
                        entries = extract_answer_key_entries(ans_part, page_num)
                        if entries:
                            all_answer_key_entries.extend(entries)
                        break

                # Deterministic layout-aware extraction
                page_qs, active_section, active_marks = extract_questions_from_page_layout(
                    raw_text=question_text,
                    page_number=page_num,
                    current_section=active_section,
                    current_marks=active_marks,
                    extraction_method=method,
                    text_quality_score=q_score,
                    character_count=char_count or len(question_text)
                )
                if page_qs and len(page_qs) > 0:
                    all_questions.extend(page_qs)
                else:
                    ai_tasks.append((page_idx, page))

        elif page_type == "image":
            # Scanned page -> Queue for Vision extraction
            ai_tasks.append((page_idx, page))

    # Step 3: Concurrently process queued AI tasks with bounded concurrency
    if ai_tasks:
        max_workers = min(len(ai_tasks), max(1, settings.max_ai_concurrency))

        def process_ai_task(task_info: tuple[int, dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
            idx, page_item = task_info
            p_num = page_item.get("page_number", idx + 1)
            p_type = page_item.get("type", "text")
            p_content = page_item.get("content")
            p_method = page_item.get("extraction_method", "OCR" if p_type == "image" else "native_text")
            p_score = page_item.get("text_quality_score", 0.95)
            p_char_count = page_item.get("character_count", 0)

            res = []
            try:
                if p_type == "text" or p_type == "dataframe":
                    res = extract_questions_from_text(str(p_content), p_num)
                else:
                    res = extract_questions_from_image(p_content, p_num)
            except Exception as e:
                print(f"Warning: AI vision extraction for page {p_num} failed: {e}")
                res = []
                
            for rq in res:
                rq.setdefault("extraction_method", p_method)
                rq.setdefault("text_quality_score", p_score)
                rq.setdefault("character_count", p_char_count or len(str(rq.get("question", ""))))
            return idx, res

        if len(ai_tasks) == 1:
            _, ai_results = process_ai_task(ai_tasks[0])
            all_questions.extend(ai_results)
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                completed = list(executor.map(process_ai_task, ai_tasks))
            completed.sort(key=lambda x: x[0])
            for _, ai_results in completed:
                all_questions.extend(ai_results)

    # Step 4: Perform Cross-Page Answer Key -> Question Mapping
    mapped_questions = map_cross_page_answers(all_questions, all_answer_key_entries)

    # Step 4b: Audit Unicode symbols, 4-option integrity, and compute granular confidence scores
    from app.services.mcq_integrity_validator import audit_and_validate_question
    audited_questions = [audit_and_validate_question(q) for q in mapped_questions]

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Step 5: Compute Extraction Statistics
    stats = compute_extraction_statistics(
        questions=audited_questions,
        pages_count=len(pages),
        elapsed_ms=elapsed_ms,
        visual_pages_count=visual_pages_count,
        pages_breakdown=pages_breakdown
    )

    # Attach stats to top-level questions metadata or first element if needed
    for q in audited_questions:
        q["extraction_stats"] = stats

    # Step 6: Save to Cache
    if settings.enable_extraction_cache and audited_questions:
        save_cached_extraction(
            file_hash,
            audited_questions,
            metadata=stats
        )

    return audited_questions


def merge_continued_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Stitches questions that continue across page boundaries.
    If a question is incomplete and the next question block contains only options or
    continuation text from the next page, merges them.
    """
    if len(questions) < 2:
        return questions

    merged = []
    i = 0
    while i < len(questions):
        q = dict(questions[i])

        while i + 1 < len(questions):
            next_q = questions[i + 1]

            same_file = q.get("source_file") == next_q.get("source_file")
            consecutive_page = (next_q.get("source_page", 0) or 0) - (q.get("source_page", 0) or 0) <= 1

            if not (same_file and consecutive_page):
                break

            # If next_q has a distinct question number from q, never merge
            q_num = q.get("question_number")
            next_num = next_q.get("question_number")
            if q_num is not None and next_num is not None and str(q_num) != str(next_num):
                break

            q_stem = (q.get("question") or "").strip()
            next_stem = (next_q.get("question") or "").strip()

            # Check if Q1 is incomplete (no options) and Q2 contains options with continuation text
            q_has_options = bool(
                q.get("options")
                or any(q.get(f"answer_{i}") for i in range(1, 5))
            )

            next_has_options = bool(
                next_q.get("options")
                or any(next_q.get(f"answer_{i}") for i in range(1, 5))
            )
            is_q1_incomplete = not q_has_options and len(q_stem) > 0
            is_q2_continuation = next_has_options and (
                not next_stem
                or next_stem[0].islower()
                or len(next_stem) < 40
                or next_stem.startswith("...")
                or "correct" in next_stem.lower()
            )

            # Check if text is split in the middle of a sentence
            is_text_split = q_stem and next_stem and (
                q_stem.endswith("-")
                or q_stem[-1] in (",", "and", "or", "of", "the", "which", "is", "are", "be")
            ) and next_stem and next_stem[0].islower()

            if (is_q1_incomplete and is_q2_continuation) or is_text_split:
                if is_text_split:
                    if q_stem.endswith("-"):
                        q["question"] = q_stem[:-1] + next_stem
                    else:
                        q["question"] = q_stem + " " + next_stem
                else:
                    q["question"] = q_stem + " " + next_stem

                if next_has_options:
                    q["options"] = next_q["options"]

                if not q.get("correct_answer") and next_q.get("correct_answer"):
                    q["correct_answer"] = next_q["correct_answer"]

                i += 1  # Skip merged question
            else:
                break

        merged.append(q)
        i += 1

    return merged


def detect_multiple_assessments(questions: list[dict[str, Any]]) -> str | None:
    """
    Analyzes vocabulary/topic differences and numbering overlap to warn if
    multiple unrelated assessments are uploaded together.
    """
    if len(questions) < 10:
        return None

    # Group by file
    by_file = {}
    for q in questions:
        by_file.setdefault(q.get("source_file", "unknown"), []).append(q)

    if len(by_file) < 2:
        return None

    # Calculate overlapping question numbers
    file_stems = {}
    for fname, qlist in by_file.items():
        stems_words = set(re.findall(r"\w+", " ".join(str(q.get("question", "")).lower() for q in qlist)))
        file_stems[fname] = stems_words

    fnames = list(by_file.keys())
    for idx1 in range(len(fnames)):
        fn1 = fnames[idx1]
        for idx2 in range(idx1 + 1, len(fnames)):
            fn2 = fnames[idx2]
            
            # Check overlap in question numbers
            nums1 = set(q.get("question_number") for q in by_file[fn1] if q.get("question_number") is not None)
            nums2 = set(q.get("question_number") for q in by_file[fn2] if q.get("question_number") is not None)
            
            # If significant numbering overlap (e.g. both have Q1-Q10)
            overlap_nums = nums1.intersection(nums2)
            if len(overlap_nums) >= 5:
                # Check topic similarity
                words1 = file_stems[fn1]
                words2 = file_stems[fn2]
                if not words1 or not words2:
                    continue
                similarity = len(words1.intersection(words2)) / len(words1.union(words2))
                # If vocabulary similarity is extremely low, they belong to different subjects
                if similarity < 0.12:
                    return f"Multiple unrelated assessments detected: '{fn1}' and '{fn2}' appear to cover different subjects or topics."

    return None


def parse_source_batch(
    files: list[dict[str, Any]],
    progress_callback: Any = None
) -> dict[str, Any]:
    """
    Concurrent multi-file extraction pipeline:
    1. Read all files page-by-page.
    2. Classify each page/section to determine role.
    3. Concurrently parse question/answer pages using bounded thread pool.
    4. Run cross-page/file Q&A Reconciliation.
    5. Audit integrity, duplicates, and multiple assessments.
    6. Return unified pool.
    """
    start_time = time.perf_counter()
    from app.services.source_classifier import classify_page_content
    from app.services.reconciliation_engine import reconcile_questions_and_answers
    from app.services.mcq_integrity_validator import audit_and_validate_question

    if progress_callback:
        progress_callback("Reading files and classifying page roles...")

    # Step 1: Read all pages from all files and classify
    all_units = []
    total_pages = 0
    
    for f in files:
        path = f["absolute_path"]
        p_name = f.get("parent_source")
        s_name = f.get("source_file")
        
        # Check cache first
        file_hash = compute_file_hash(path)
        cached_qs = get_cached_extraction(file_hash) if settings.enable_extraction_cache else None
        
        pages = read_source_pages(path)
        total_pages += len(pages)
        
        for p_idx, page in enumerate(pages):
            p_num = page.get("page_number", p_idx + 1)
            p_type = page.get("type", "text")
            content = page.get("content")
            
            is_df = (p_type == "dataframe")
            classification = classify_page_content(
                text=str(content) if p_type == "text" or is_df else "",
                page_number=p_num,
                filename=s_name,
                is_dataframe=is_df
            )
            
            unit = {
                "absolute_path": path,
                "parent_source": p_name,
                "source_file": s_name,
                "page_number": p_num,
                "content": content,
                "df": page.get("df"),
                "type": p_type,
                "has_visual": page.get("has_visual", False),
                "role": classification["role"],
                "confidence_score": classification["confidence_score"],
                "confidence_label": classification["confidence_label"],
                "cached_qs": cached_qs
            }
            all_units.append(unit)

    # Step 2: Concurrently extract questions and answers
    extracted_questions = []
    extracted_answers = []
    
    # Track units requiring AI fallback parsing
    ai_tasks = []
    
    for idx, unit in enumerate(all_units):
        cached_qs = unit.get("cached_qs")
        if cached_qs:
            # Re-use cached extraction directly
            for q in cached_qs:
                q["source_file"] = unit["source_file"]
                q["parent_source"] = unit["parent_source"]
                q["source_page"] = unit["page_number"]
            extracted_questions.extend(cached_qs)
            continue
            
        role = unit["role"]
        p_type = unit["type"]
        p_num = unit["page_number"]
        content = unit["content"]
        s_name = unit["source_file"]
        p_name = unit["parent_source"]

        # Parse questions
        if role in ("QUESTION_SOURCE", "MIXED_SOURCE", "UNKNOWN_SOURCE"):
            if p_type == "dataframe" and "df" in unit and unit["df"] is not None:
                df_qs = extract_questions_from_dataframe(unit["df"], p_num)
                for q in df_qs:
                    q["source_file"] = s_name
                    q["parent_source"] = p_name
                    q["source_page"] = p_num
                extracted_questions.extend(df_qs)
            elif p_type == "text":
                text_str = str(content).strip()
                page_qs = extract_questions_from_page_layout(
                    raw_text=text_str,
                    page_number=p_num,
                    extraction_method=unit.get("extraction_method", "OCR"),
                    text_quality_score=unit.get("text_quality_score", 1.0),
                    character_count=len(text_str)
                )[0]
                if page_qs:
                    for q in page_qs:
                        q["source_file"] = s_name
                        q["parent_source"] = p_name
                        q["source_page"] = p_num
                    extracted_questions.extend(page_qs)
                else:
                    ai_tasks.append((idx, "question"))
            elif p_type == "image":
                ai_tasks.append((idx, "question"))

        # Parse answers
        if role in ("ANSWER_SOURCE", "MIXED_SOURCE"):
            if p_type == "text":
                text_str = str(content).strip()
                entries = extract_answer_key_entries(text_str, p_num, chapter_name=s_name)
                if entries:
                    for a in entries:
                        a["source_file"] = s_name
                        a["parent_source"] = p_name
                        a["source_page"] = p_num
                        a["source_role"] = role
                    extracted_answers.extend(entries)
                else:
                    ai_tasks.append((idx, "answer"))
            elif p_type == "image":
                ai_tasks.append((idx, "answer"))

    # Process AI fallback tasks with bounded concurrency (3 concurrent workers)
    if ai_tasks:
        max_workers = min(len(ai_tasks), max(1, settings.max_ai_concurrency, 3))
        if progress_callback:
            progress_callback(f"Running concurrent AI parsing on {len(ai_tasks)} pages...")

        def execute_ai_extraction(task):
            unit_idx, task_type = task
            unit = all_units[unit_idx]
            p_num = unit["page_number"]
            p_type = unit["type"]
            content = unit["content"]
            s_name = unit["source_file"]
            p_name = unit["parent_source"]
            
            res_list = []
            if task_type == "question":
                try:
                    if p_type == "image":
                        res_list = extract_questions_from_image(content, p_num)
                    else:
                        res_list = extract_questions_from_text(str(content), p_num)
                except Exception as e:
                    print(f"Warning: AI vision extraction for {s_name} (page {p_num}) failed: {e}")
                    res_list = []

                for q in res_list:
                    q["source_file"] = s_name
                    q["parent_source"] = p_name
                    q["source_page"] = p_num
                    q.setdefault("extraction_method", "OCR")
                    q.setdefault("text_quality_score", 0.95)
                    q.setdefault("character_count", len(str(q.get("question", ""))))
            else:
                # Answer OCR/parsing fallback using OpenAI (structured text prompt)
                prompt = f"Extract all answer key entries from this page text. Return JSON array."
                if p_type == "image":
                    extracted_text = ""
                    try:
                        client = get_client()
                        import base64
                        base64_image = base64.b64encode(content).decode("utf-8")
                        response = _call_azure_with_retry(
                            client,
                            {
                                "model": settings.azure_openai_deployment_name,
                                "messages": [
                                    {"role": "system", "content": "You are a precise OCR transcriber. Transcribe all text on the image exactly."},
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "text", "text": "Transcribe text."},
                                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                                        ]
                                    }
                                ]
                            }
                        )
                        extracted_text = response.choices[0].message.content or ""
                    except Exception as e:
                        print(f"Warning: Image OCR fallback failed: {e}")
                else:
                    extracted_text = str(content)
                    
                res_list = extract_answer_key_entries(extracted_text, p_num, chapter_name=s_name)
                for a in res_list:
                    a["source_file"] = s_name
                    a["parent_source"] = p_name
                    a["source_page"] = p_num
                    a["source_role"] = unit["role"]
                    
            return task_type, res_list

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            thread_results = list(executor.map(execute_ai_extraction, ai_tasks))
            
        for task_type, res_list in thread_results:
            if task_type == "question":
                extracted_questions.extend(res_list)
            else:
                extracted_answers.extend(res_list)

    if progress_callback:
        progress_callback("Merging continued question pages...")

    # Step 3: Stitch question blocks across pages
    extracted_questions = merge_continued_questions(extracted_questions)

    if progress_callback:
        progress_callback("Running multi-source reconciliation matching...")

    # Step 4: Reconcile Questions and Answers
    reconciled = reconcile_questions_and_answers(extracted_questions, extracted_answers)

    # Step 5: Audit Unicode and format choices
    audited = [audit_and_validate_question(q) for q in reconciled]

    # Step 6: Multiple Assessment Warning detection
    warning_msg = detect_multiple_assessments(audited)

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    
    # Statistics
    stats = {
        "pages_processed": total_pages,
        "total_questions_detected": len(audited),
        "total_answers_detected": len(extracted_answers),
        "matched": sum(1 for q in audited if q.get("source_answer_key") is not None),
        "needs_review": sum(1 for q in audited if q.get("review_required") or q.get("status") == "REVIEW_REQUIRED"),
        "duplicates": sum(1 for q in audited if "DUPLICATE" in str(q.get("validation_status", ""))),
        "extraction_time_ms": elapsed_ms
    }

    # Attach stats to questions
    for q in audited:
        q["extraction_stats"] = stats

    return {
        "questions": audited,
        "statistics": stats,
        "warning": warning_msg,
        "files_processed": len(files)
    }

