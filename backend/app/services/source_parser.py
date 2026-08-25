import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from app.config import settings
from app.services.source_reader import read_source_pages
from app.services.azure_openai import extract_questions_from_text, extract_questions_from_image
from app.services.deterministic_parser import (
    extract_questions_from_structured_text,
    extract_questions_from_dataframe,
)
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

def parse_source_document(path: str) -> list[dict[str, Any]]:
    """
    High-performance question and cross-page answer key extraction pipeline:
    1. Checks SHA-256 content hash cache for instant retrieval.
    2. Segregates Question Content pages and Answer Key pages.
    3. Performs local deterministic parsing first for machine-readable text/tables.
    4. Invokes Azure OpenAI concurrently only for image/unstructured pages where needed.
    5. Performs cross-page / cross-section deterministic question-to-answer mapping.
    6. Caches verified extraction and mapping results.
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

    # Pages that require AI processing for question extraction
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

            # Check if this page is an explicit Answer Key section/page
            if is_answer_key_text(text_str):
                # Extract Answer Key Entries - Do NOT treat as questions!
                entries = extract_answer_key_entries(text_str, page_num)
                if entries:
                    all_answer_key_entries.extend(entries)
            else:
                # Deterministic local question extraction
                deterministic_qs = extract_questions_from_structured_text(text_str, page_num)
                if deterministic_qs and len(deterministic_qs) > 0:
                    all_questions.extend(deterministic_qs)
                else:
                    # Text could not be parsed deterministically -> Queue for AI extraction
                    ai_tasks.append((page_idx, page))

        elif page_type == "image":
            # Scanned or image page -> Queue for Vision extraction
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
            # Sort by original page index to maintain correct page order
            completed.sort(key=lambda x: x[0])
            for _, ai_results in completed:
                all_questions.extend(ai_results)

    # Step 4: Perform Cross-Page Answer Key -> Question Mapping
    mapped_questions = map_cross_page_answers(all_questions, all_answer_key_entries)

    # Step 5: Save to Cache
    if settings.enable_extraction_cache and mapped_questions:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        save_cached_extraction(
            file_hash,
            mapped_questions,
            metadata={
                "extraction_time_ms": elapsed_ms,
                "question_count": len(mapped_questions),
                "answer_key_entries_count": len(all_answer_key_entries)
            }
        )

    return mapped_questions
