import json
import base64
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from openai import AzureOpenAI
from app.config import settings

class AzureOpenAIError(Exception):
    pass

def get_client() -> AzureOpenAI:
    if not settings.azure_openai_api_key or not settings.azure_openai_endpoint:
        raise AzureOpenAIError(
            "Azure OpenAI is not configured. Please supply AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT."
        )
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_openai_deployment_name
    )

def get_critic_client() -> tuple[AzureOpenAI, str]:
    """
    Returns an AzureOpenAI client and deployment name for the critic pass.
    Uses separate critic deployment if configured, otherwise falls back to primary client.
    """
    if not settings.azure_openai_api_key or not settings.azure_openai_endpoint:
        raise AzureOpenAIError(
            "Azure OpenAI is not configured. Please supply AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT."
        )
    critic_dep = settings.azure_openai_critic_deployment_name.strip()
    if critic_dep:
        api_ver = settings.azure_openai_critic_api_version.strip() or settings.azure_openai_api_version
        client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=api_ver,
            azure_endpoint=settings.azure_openai_endpoint,
            azure_deployment=critic_dep
        )
        return client, critic_dep
    return get_client(), settings.azure_openai_deployment_name

def _call_azure_with_retry(client: AzureOpenAI, create_kwargs: dict[str, Any], max_retries: int = 3, base_delay: float = 1.0):
    """Executes chat completion with exponential backoff on rate-limit (429) or transient errors."""
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(**create_kwargs)
        except Exception as e:
            err_str = str(e)
            is_transient = "429" in err_str or "503" in err_str or "500" in err_str or "rate limit" in err_str.lower()
            if is_transient and attempt < max_retries - 1:
                sleep_time = base_delay * (2 ** attempt)
                time.sleep(sleep_time)
            else:
                raise

SYSTEM_PROMPT = """You are a highly precise semantic question extraction assistant.
Your task is to extract questions and answers from the provided source material and structure them.

Rules:
- DO NOT generate new, unrelated questions. Only extract questions directly from the provided source.
- Preserve source question wording and options as faithfully as possible without rewriting.
- Extract ALL questions present in the source without arbitrary limits.
- Preserve all Unicode scientific and mathematical symbols exactly (e.g., λ, μ, γ, ω, θ, π, α, β, Ω, °, ±, ≤, ≥, ×, ÷, μF, kΩ, H₂O, superscripts, subscripts).
- Never replace mathematical symbols with control characters or mangled approximations (e.g., do not write 'bcF' for 'μF' or 'ac9' for 'ω' or '90b0' for '90°').
- For MCQ questions, populate the options array with exactly the options present in the source.
- Return ONLY a JSON object matching the requested schema.
"""

def extract_questions_from_text(text: str, page_number: int | None = None) -> list[dict[str, Any]]:
    client = get_client()
    
    prompt = f"""Extract all questions from the text source below.
If a page number is known, associate it with the questions.

Return JSON in this format:
{{
  "questions": [
    {{
      "question": "...",
      "options": ["option 1", "option 2", "option 3", "option 4"],
      "correct_answer": "...",
      "topic": "...",
      "subtopic": "...",
      "difficulty": "Easy/Medium/Hard",
      "score": "1",
      "starter_code": "...",
      "expected_output": "...",
      "test_cases": "...",
      "source_page": {page_number if page_number is not None else "null"}
    }}
  ]
}}

SOURCE TEXT:
{text}
"""
    try:
        response = _call_azure_with_retry(
            client,
            {
                "model": settings.azure_openai_deployment_name,
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            }
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return payload.get("questions", [])
    except Exception as e:
        raise AzureOpenAIError(f"Azure OpenAI extraction failed: {e}")

def extract_questions_from_image(image_bytes: bytes, page_number: int | None = None) -> list[dict[str, Any]]:
    client = get_client()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    
    prompt = f"""Extract all questions from this image/scanned document page.
Return JSON in this format:
{{
  "questions": [
    {{
      "question": "...",
      "options": ["option 1", "option 2", "option 3", "option 4"],
      "correct_answer": "...",
      "topic": "...",
      "subtopic": "...",
      "difficulty": "Easy/Medium/Hard",
      "score": "1",
      "starter_code": "...",
      "expected_output": "...",
      "test_cases": "...",
      "source_page": {page_number if page_number is not None else "null"}
    }}
  ]
}}
"""
    try:
        response = _call_azure_with_retry(
            client,
            {
                "model": settings.azure_openai_deployment_name,
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ]
            }
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return payload.get("questions", [])
    except Exception as e:
        raise AzureOpenAIError(f"Azure OpenAI Vision extraction failed: {e}")

def infer_missing_fields_and_map(extracted_questions: list[dict], template_schema: dict) -> list[dict]:
    """
    Takes questions and normalizes them against template columns.
    Batches questions in chunks of 10 and processes chunks concurrently using bounded ThreadPoolExecutor.
    Preserves exact order of mapped questions.
    """
    client = get_client()
    columns_info = template_schema.get("column_schema", [])
    chunk_size = 10

    chunks = [
        (i, extracted_questions[i:i + chunk_size])
        for i in range(0, len(extracted_questions), chunk_size)
    ]

    if not chunks:
        return []

    def process_chunk(chunk_info: tuple[int, list[dict]]) -> tuple[int, list[dict]]:
        chunk_start, chunk = chunk_info
        prompt = f"""You are a question mapping and inference engine.
You have a set of extracted question dictionaries, and a target template schema.
Your task is to:
1. Map each question's properties to the target template columns.
2. If a required or optional column in the template is missing from a question, try to infer it.
   - For example, if Topic/Subtopic is missing, infer it from the question content.
   - If Difficulty is missing, infer it as Easy, Medium, Hard.
   - If options are MCQs and target template has separate columns like Option 1, Option 2, Option A, Option B, distribute them accurately.
   - DO NOT fabricate factual content (like starter code or test cases if not in the source). Leave them empty.
3. For each mapped field, track the origin: "extracted" (explicitly in source), "inferred" (confidently derived), or "missing" (empty/not obtainable).
4. Assign a confidence score from 0.0 to 1.0 for each field.

TARGET TEMPLATE COLUMNS:
{json.dumps(columns_info, indent=2)}

EXTRACTED QUESTIONS CHUNK (Starting at index {chunk_start + 1}):
{json.dumps(chunk, indent=2)}

Return JSON in this format:
{{
  "mapped_questions": [
    {{
      "row_number": 1,
      "data": {{
         "Original Column Name": "mapped value or inferred value or empty string"
      }},
      "metadata": {{
         "Original Column Name": {{
            "origin": "extracted" | "inferred" | "missing",
            "confidence": 0.95
         }}
      }},
      "source_page": 12
    }}
  ]
}}
"""
        try:
            response = _call_azure_with_retry(
                client,
                {
                    "model": settings.azure_openai_deployment_name,
                    "temperature": 0.0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": "You map fields and perform semantic inference with confidence scores."},
                        {"role": "user", "content": prompt}
                    ]
                }
            )
            content = response.choices[0].message.content or "{}"
            payload = json.loads(content)
            return chunk_start, payload.get("mapped_questions", [])
        except Exception as e:
            raise AzureOpenAIError(f"Azure OpenAI mapping and inference failed: {e}")

    max_workers = min(len(chunks), max(1, settings.max_ai_concurrency))
    all_mapped_questions = []

    if len(chunks) == 1:
        _, mapped = process_chunk(chunks[0])
        all_mapped_questions = mapped
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            chunk_results = list(executor.map(process_chunk, chunks))
        # Ensure correct sequential ordering
        chunk_results.sort(key=lambda x: x[0])
        for _, mapped in chunk_results:
            all_mapped_questions.extend(mapped)

    return all_mapped_questions

AI_FILL_CONFIDENCE_THRESHOLD = 0.70  # Minimum confidence to auto-persist a field

def fill_missing_fields_for_single_question(
    question_data: dict[str, Any],
    missing_fields: list[str],
    template_schema: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Resolves ALL missing metadata fields for a single assessment question in ONE AI call.

    Args:
        question_data: The question's current data_json (column -> value mapping).
        missing_fields: List of field names that are genuinely empty and need to be inferred.
                        Only truly-empty fields should be passed — not all columns.
        template_schema: The template column_schema list (for field type context).
        context: Batch context (subject, gradeClass, chapterTopic, questionType).

    Returns:
        dict mapping field_name -> {value, status, confidence, reason}
        Every field in missing_fields is guaranteed to have an entry.
        Fields that could not be safely inferred have status="UNRESOLVED" and value=None.
    """
    if not missing_fields:
        return {}

    client = get_client()
    ctx_info = context or {}

    import logging
    logger = logging.getLogger("ai_fill")

    question_id_hint = question_data.get("id") or question_data.get("question_id") or "unknown"

    logger.info(
        "AI_FILL_REQUEST | question_id=%s | requested_fields=%s",
        question_id_hint,
        missing_fields,
    )

    # Build a field-type context string from template schema
    schema_context = ""
    if template_schema:
        col_schema = template_schema.get("column_schema", [])
        field_hints = []
        for col in col_schema:
            if col.get("original_name") in missing_fields:
                hint = f"  - {col.get('original_name')}"
                if col.get("example_value"):
                    hint += f" (example: \"{col['example_value']}\")"
                if col.get("required"):
                    hint += " [REQUIRED]"
                field_hints.append(hint)
        if field_hints:
            schema_context = "FIELD TYPE HINTS FROM TEMPLATE:\n" + "\n".join(field_hints) + "\n\n"

    # Serialize the existing question data for context (mask the id fields)
    question_context = {k: v for k, v in question_data.items()
                        if k not in ("id", "question_id") and v not in (None, "", [])}

    system_prompt = (
        "You are a precise educational assessment metadata expert.\n"
        "Your task is to infer missing metadata fields for a single assessment question.\n\n"
        "CRITICAL RULES:\n"
        "1. Return a result for EVERY field listed in REQUESTED_FIELDS — no exceptions.\n"
        "2. Do NOT omit any requested field from your response.\n"
        "3. If a field can be reliably inferred from the question content and context, "
        "set status to 'AI_INFERRED' with your best value and a confidence score.\n"
        "4. If a field genuinely cannot be inferred without additional information, "
        "set status to 'UNRESOLVED', value to null, and explain why in reason.\n"
        "5. Do NOT fabricate information. Do NOT invent values to make the form look complete.\n"
        "6. Do NOT assign generic default values (such as 'Medium' for difficulty, '1' for score, '60' for time limit) "
        "unless they are actually defined or strongly justified by the question content, source material, or templates.\n"
        "7. Preserve any source-derived information. Never overwrite source answers.\n"
        "8. Base inferences only on the question text, options, subject, and context provided.\n"
        "9. Confidence must be a float between 0.0 and 1.0 reflecting your certainty.\n"
    )

    prompt = f"""You are resolving ALL missing fields for a single assessment question in ONE complete operation.

ASSESSMENT CONTEXT:
Subject: {ctx_info.get('subject', 'General')}
Grade/Class: {ctx_info.get('gradeClass', 'General')}
Chapter/Topic: {ctx_info.get('chapterTopic', 'General')}
Question Type: {ctx_info.get('questionType', 'General')}

{schema_context}EXISTING QUESTION DATA (already populated fields — DO NOT overwrite these):
{json.dumps(question_context, indent=2)}

REQUESTED_FIELDS (you MUST return an entry for EVERY one of these):
{json.dumps(missing_fields, indent=2)}

INSTRUCTIONS:
- Evaluate EACH requested field independently.
- For each field: infer from question text, options, subject, context, and any available clues.
- If you can confidently infer a value: status = "AI_INFERRED", provide value and confidence >= 0.70.
- If you cannot safely infer: status = "UNRESOLVED", value = null, confidence < 0.70, explain in reason.
- Do NOT use generic fallback default values (e.g. Difficulty = Medium) if there is no evidence to support them.
- Return EXACTLY one entry per requested field. Never skip a field.

Return ONLY this JSON structure (no other text):
{{
  "fields": {{
    "<exact_field_name_from_REQUESTED_FIELDS>": {{
      "value": "<inferred value or null>",
      "status": "AI_INFERRED" | "UNRESOLVED",
      "confidence": 0.0,
      "reason": "<brief explanation of inference basis or why it cannot be inferred>"
    }}
  }}
}}
"""

    try:
        response = _call_azure_with_retry(
            client,
            {
                "model": settings.azure_openai_deployment_name,
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        raw_fields = payload.get("fields", {})

        logger.info(
            "AI_FILL_RESPONSE | question_id=%s | returned_fields=%s",
            question_id_hint,
            list(raw_fields.keys()),
        )

        # Helper to normalize key for robust matching
        def clean_key(k: str) -> str:
            return "".join(c for c in k.lower() if c.isalnum())

        normalized_raw = {}
        for rk, rv in raw_fields.items():
            normalized_raw[clean_key(rk)] = rk

        # Normalize and validate: ensure every requested field has an entry
        result: dict[str, dict[str, Any]] = {}
        resolved = []
        unresolved = []

        for field_name in missing_fields:
            norm_field = clean_key(field_name)
            matched_rk = None

            # 1. Exact match
            if field_name in raw_fields:
                matched_rk = field_name
            # 2. Normalized match
            elif norm_field in normalized_raw:
                matched_rk = normalized_raw[norm_field]
            # 3. Fuzzy match: check if norm_field is part of any raw key or vice versa
            else:
                for nrk, rk in normalized_raw.items():
                    if norm_field in nrk or nrk in norm_field:
                        matched_rk = rk
                        break

            if matched_rk is not None:
                entry = raw_fields[matched_rk]
                value = entry.get("value")
                status = entry.get("status", "UNRESOLVED")
                confidence = float(entry.get("confidence", 0.0))
                reason = entry.get("reason", "")

                # Normalize value: treat empty string, "null", "undefined" as None
                if value is not None:
                    value = str(value).strip()
                    if value.lower() in ("null", "undefined", "none", "", "n/a", "na", "-", "--", "unresolved", "[unresolved]"):
                        value = None

                # Specific field validations
                norm_name = field_name.lower().strip()
                if value is not None:
                    # Difficulty validation
                    if norm_name in ("difficulty", "difficulty level", "diff", "level"):
                        uval = value.upper()
                        if uval in ("EASY", "MEDIUM", "HARD"):
                            value = value.capitalize()
                        elif "easy" in norm_name or "easy" in value.lower():
                            value = "Easy"
                        elif "hard" in norm_name or "hard" in value.lower():
                            value = "Hard"
                        elif "med" in value.lower():
                            value = "Medium"
                        else:
                            value = value.capitalize()
                    # Numeric fields validation (e.g. marks, score)
                    elif norm_name in ("marks", "score", "points", "mark", "weightage"):
                        import re
                        m = re.search(r"\d+(?:\.\d+)?", str(value))
                        if m:
                            value = m.group(0)
                        else:
                            status = "UNRESOLVED"
                            confidence = min(confidence, 0.4)

                # If value is None, force UNRESOLVED
                if value is None:
                    status = "UNRESOLVED"
                    confidence = min(confidence, 0.5)

                result[field_name] = {
                    "value": value,
                    "status": status,
                    "confidence": round(min(1.0, max(0.0, confidence)), 4),
                    "reason": reason,
                }

                if status == "AI_INFERRED" and value:
                    resolved.append(field_name)
                else:
                    unresolved.append(field_name)
            else:
                # AI did not return this field at all — mark as UNRESOLVED
                result[field_name] = {
                    "value": None,
                    "status": "UNRESOLVED",
                    "confidence": 0.0,
                    "reason": "Field was not returned by AI inference model.",
                }
                unresolved.append(field_name)

        logger.info(
            "AI_FILL_VALIDATION | question_id=%s | resolved=%s | unresolved=%s",
            question_id_hint,
            resolved,
            unresolved,
        )

        return result

    except Exception as e:
        logger.error("AI_FILL_ERROR | question_id=%s | error=%s", question_id_hint, str(e))
        raise AzureOpenAIError(f"AI Fill Missing Fields (single question) failed: {e}")


def fill_missing_fields_for_questions(
    questions: list[dict],
    fields_to_fill: list[str],
    context: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Intelligently generates field values for missing schema columns (e.g. topic, difficulty, blooms_taxonomy)
    based on available question content, options, subject, and chapter.
    Does NOT invent source facts. If uncertain, marks status as 'UNRESOLVED'.
    """
    client = get_client()
    ctx_info = context or {}
    
    prompt = f"""You are an AI Assessment Quality Assistant.
Your task is to propose values for specific missing metadata fields for each question below.

CONTEXT:
Subject: {ctx_info.get('subject', 'General')}
Grade/Class: {ctx_info.get('gradeClass', 'General')}
Chapter/Topic: {ctx_info.get('chapterTopic', 'General')}

FIELDS TO POPULATE:
{json.dumps(fields_to_fill, indent=2)}

QUESTIONS:
{json.dumps(questions, indent=2)}

RULES:
- Propose values ONLY if a reasonable inference can be made from question text, options, and context.
- For Difficulty: use 'Easy', 'Medium', or 'Hard'.
- If a field CANNOT be reliably inferred, set value to null, status to 'UNRESOLVED', and provide a reason.
- Assign a confidence score between 0.0 and 1.0.

Return JSON in this format:
{{
  "suggestions": [
    {{
      "question_id": "...",
      "fields": {{
        "field_name": {{
          "value": "...",
          "status": "AI_INFERRED" | "UNRESOLVED",
          "confidence": 0.95,
          "reason": "Derived from quadratic formula present in question stem"
        }}
      }}
    }}
  ]
}}
"""
    try:
        response = _call_azure_with_retry(
            client,
            {
                "model": settings.azure_openai_deployment_name,
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "You are a precise educational assessment metadata assistant."},
                    {"role": "user", "content": prompt}
                ]
            }
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return payload.get("suggestions", [])
    except Exception as e:
        raise AzureOpenAIError(f"AI Fill Missing Fields failed: {e}")

def map_fields_via_ai(
    source_fields: list[str],
    target_fields: list[str],
    context: dict[str, Any] | None = None
) -> dict[str, dict[str, Any]]:
    """
    Calls Azure OpenAI to determine semantic mapping between unresolved source fields and target fields.
    """
    if not source_fields or not target_fields:
        return {}

    client = get_client()
    ctx_info = context or {}

    prompt = f"""You are a precise database schema mapping assistant.
Your task is to map unresolved source fields from an extracted question structure to the target template columns.

ASSESSMENT CONTEXT:
Subject: {ctx_info.get('subject', 'General')}
Question Type: {ctx_info.get('questionType', 'General')}

UNRESOLVED SOURCE FIELDS:
{json.dumps(source_fields, indent=2)}

TARGET TEMPLATE COLUMNS:
{json.dumps(target_fields, indent=2)}

INSTRUCTIONS:
1. Try to map each target column to the most semantically appropriate source field.
2. Only suggest a mapping if there is a strong semantic relationship.
3. For each mapped target column, assign a confidence score between 0.0 and 1.0.
4. Do NOT map a target column if no source field fits.

Return ONLY this JSON structure (no other text):
{{
  "mappings": [
    {{
      "source": "<source_field_name>",
      "target": "<target_column_name>",
      "confidence": 0.95
    }}
  ]
}}
"""
    try:
        response = _call_azure_with_retry(
            client,
            {
                "model": settings.azure_openai_deployment_name,
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "You map unresolved database schema columns precisely."},
                    {"role": "user", "content": prompt}
                ]
            }
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        mappings_list = payload.get("mappings", [])
        
        result = {}
        for m in mappings_list:
            src = m.get("source")
            tgt = m.get("target")
            conf = float(m.get("confidence", 0.8))
            if src and tgt:
                result[tgt] = {
                    "source": src,
                    "confidence": conf
                }
        return result
    except Exception as e:
        import logging
        logger = logging.getLogger("ai_mapping")
        logger.error("AI_SEMANTIC_MAPPING_ERROR | error=%s", str(e))
        return {}
