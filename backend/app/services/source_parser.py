import time
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
    visual_pages_count: int
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

    # Pages requiring AI fallback
    ai_tasks: list[tuple[int, dict[str, Any]]] = []

    for page_idx, page in enumerate(pages):
        page_num = page.get("page_number", page_idx + 1)
        page_type = page.get("type", "text")
        content = page.get("content")

        if page_type == "dataframe" and "df" in page:
            # Deterministic tabular extraction
            df_questions = extract_questions_from_dataframe(page["df"], page_num)
            if df_questions:
                all_questions.extend(df_questions)
            else:
                ai_tasks.append((page_idx, page))

        elif page_type == "text":
            text_str = str(content or "").strip()
            if not text_str:
                continue

            # Check if this page is an Answer Key page
            if is_answer_key_text(text_str):
                entries = extract_answer_key_entries(text_str, page_num)
                if entries:
                    all_answer_key_entries.extend(entries)
            else:
                # Deterministic layout-aware extraction
                page_qs, active_section, active_marks = extract_questions_from_page_layout(
                    raw_text=text_str,
                    page_number=page_num,
                    current_section=active_section,
                    current_marks=active_marks
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

            if p_type == "text" or p_type == "dataframe":
                res = extract_questions_from_text(str(p_content), p_num)
            else:
                res = extract_questions_from_image(p_content, p_num)
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
        visual_pages_count=visual_pages_count
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
