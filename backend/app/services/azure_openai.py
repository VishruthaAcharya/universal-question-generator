import json
import base64
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

SYSTEM_PROMPT = """You are a highly precise semantic question extraction assistant.
Your task is to extract questions and answers from the provided source material and structure them.

Rules:
- DO NOT generate new, unrelated questions. Only extract questions directly from the provided source.
- Preserve code indentation, mathematical notation, and tables exactly.
- For MCQ questions, populate the options array. Keep formatting clean.
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
        response = client.chat.completions.create(
            model=settings.azure_openai_deployment_name,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
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
        response = client.chat.completions.create(
            model=settings.azure_openai_deployment_name,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
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
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return payload.get("questions", [])
    except Exception as e:
        raise AzureOpenAIError(f"Azure OpenAI Vision extraction failed: {e}")

def infer_missing_fields_and_map(extracted_questions: list[dict], template_schema: dict) -> list[dict]:
    """
    Takes questions and normalizes them, comparing them against the template columns.
    Uses Azure OpenAI to infer missing fields semantic mapping where possible.
    """
    client = get_client()
    columns_info = template_schema.get("column_schema", [])
    
    # We want to request Azure OpenAI to map extracted questions to template columns,
    # and infer missing fields.
    prompt = f"""You are a question mapping and inference engine.
You have a set of extracted question dictionaries, and a target template schema.
Your task is to:
1. Map each question's properties to the target template columns.
2. If a required or optional column in the template is missing from a question, try to infer it.
   - For example, if Topic/Subtopic is missing, infer it from the question content (e.g. Electric Charges and Fields, Coulomb's Law).
   - If Difficulty is missing, infer it as Easy, Medium, Hard.
   - If options are MCQs and target template has separate columns like Option 1, Option 2, distribute them.
   - DO NOT fabricate factual content (like starter code or test cases if not in the source). Leave them null or empty.
3. For each mapped field, track the origin: "extracted" (explicitly in source), "inferred" (confidently derived), or "missing" (empty/not obtainable).
4. Assign a confidence score from 0.0 to 1.0 for each field.

TARGET TEMPLATE COLUMNS:
{json.dumps(columns_info, indent=2)}

EXTRACTED QUESTIONS:
{json.dumps(extracted_questions, indent=2)}

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
        response = client.chat.completions.create(
            model=settings.azure_openai_deployment_name,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You map fields and perform semantic inference with confidence scores."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return payload.get("mapped_questions", [])
    except Exception as e:
        raise AzureOpenAIError(f"Azure OpenAI mapping and inference failed: {e}")
