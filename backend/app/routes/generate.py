import os
import json
import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Template, QuestionSet, Question
from app.services.template import read_template_schema, normalize_field_name
from app.services.source_parser import parse_source_document
from app.services.validator import validate_compatibility, validate_question_row, validate_questions_batch

router = APIRouter(prefix="/api", tags=["generation"])

STORAGE_DIR = Path("storage/templates")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

_TEMPLATE_SCHEMA_CACHE = {}


def _build_question_response(q: Question) -> dict:
    """Shared helper: build the canonical question response dict from a Question ORM object."""
    return {
        "id": q.id,
        "row_number": q.row_number,
        "data_json": q.data_json,
        "validation": q.validation_json,
        "source_metadata": q.source_metadata_json,
        "status": q.status,
        "source_answer": q.validation_json.get("ai_validation", {}).get("source_answer") if q.validation_json else None,
        "ai_answer": q.validation_json.get("ai_validation", {}).get("ai_answer") if q.validation_json else None,
        "final_answer": q.data_json.get("Correct Answer") or q.data_json.get("correct_answer"),
        "answer_source": q.source_metadata_json.get("answer_source") if q.source_metadata_json else "EXPLICIT_ANSWER_KEY",
        "answer_page": q.source_metadata_json.get("answer_page") if q.source_metadata_json else None,
        "answer_section": q.source_metadata_json.get("answer_section") if q.source_metadata_json else None,
        "mapping_confidence": q.source_metadata_json.get("mapping_confidence") if q.source_metadata_json else 0.95,
        "answer_mapping_status": q.source_metadata_json.get("answer_mapping_status") if q.source_metadata_json else "ANSWER_MAPPED",
        "mapping_reason": q.source_metadata_json.get("mapping_reason") if q.source_metadata_json else None,
    }



def compute_schema_fingerprint(schema: dict) -> str:
    canonical = {
        "columns": [str(c).strip().lower() for c in schema.get("columns", [])],
        "column_schema": [
            {
                "original_name": str(c.get("original_name")).strip().lower(),
                "normalized_name": str(c.get("normalized_name")).strip().lower(),
                "required": c.get("required")
            }
            for c in sorted(schema.get("column_schema", []), key=lambda x: str(x.get("original_name", "")).strip().lower())
        ]
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode("utf-8")).hexdigest()

async def save_upload(upload: UploadFile) -> str:
    fd, path = tempfile.mkstemp(suffix=Path(upload.filename or "").suffix)
    os.close(fd)
    with open(path, "wb") as f:
        f.write(await upload.read())
    return path

@router.get("/templates")
def list_templates(include_archived: bool = False, db: Session = Depends(get_db)):
    query = db.query(Template).order_by(Template.created_at.desc())
    templates = query.all()
    
    result = []
    for t in templates:
        schema = t.schema_json or {}
        is_archived = schema.get("is_archived", False)
        if is_archived and not include_archived:
            continue
        result.append({
            "id": t.id,
            "name": t.name,
            "original_filename": t.original_filename,
            "sheet_name": t.sheet_name,
            "schema": schema,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "usage_count": len(t.question_sets),
            "is_archived": is_archived,
            "fingerprint": compute_schema_fingerprint(schema)
        })
    return result

@router.get("/templates/{template_id}")
def get_template(template_id: str, db: Session = Depends(get_db)):
    t = db.get(Template, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    schema = t.schema_json or {}
    return {
        "id": t.id,
        "name": t.name,
        "original_filename": t.original_filename,
        "sheet_name": t.sheet_name,
        "schema": schema,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "usage_count": len(t.question_sets),
        "is_archived": schema.get("is_archived", False),
        "fingerprint": compute_schema_fingerprint(schema)
    }

@router.delete("/templates/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db)):
    global _TEMPLATE_SCHEMA_CACHE
    if template_id in _TEMPLATE_SCHEMA_CACHE:
        del _TEMPLATE_SCHEMA_CACHE[template_id]

    t = db.get(Template, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Check if template is referenced by existing question sets
    if len(t.question_sets) > 0:
        # Soft-archive
        schema = dict(t.schema_json or {})
        schema["is_archived"] = True
        t.schema_json = schema
        db.commit()
        return {
            "action": "archived",
            "message": f"Template '{t.name}' was archived because it is referenced by {len(t.question_sets)} existing assessment batch(es)."
        }
    else:
        # Physical delete
        db.delete(t)
        db.commit()
        return {
            "action": "deleted",
            "message": f"Template '{t.name}' has been permanently deleted from your library."
        }

@router.post("/templates/upload")
async def upload_template(file: UploadFile = File(...), db: Session = Depends(get_db)):
    path = await save_upload(file)
    try:
        schema = read_template_schema(path)
        new_fp = compute_schema_fingerprint(schema)
        
        # Check for duplicate template in database
        existing_templates = db.query(Template).all()
        for t in existing_templates:
            existing_schema = t.schema_json or {}
            if not existing_schema.get("is_archived", False):
                if compute_schema_fingerprint(existing_schema) == new_fp:
                    return {
                        "is_duplicate": True,
                        "template_id": t.id,
                        "name": t.name,
                        "original_filename": t.original_filename,
                        "schema": existing_schema,
                        "message": f"Template already exists as '{t.name}'."
                    }
        
        # Save new unique Template to Database
        tpl = Template(
            name=Path(file.filename or "template").stem,
            original_filename=file.filename,
            sheet_name=schema.get("sheet_name"),
            schema_json=schema
        )
        db.add(tpl)
        db.flush()
        
        dest_path = STORAGE_DIR / f"{tpl.id}{Path(file.filename or '').suffix}"
        Path(path).rename(dest_path)
        
        db.commit()
        return {
            "is_duplicate": False,
            "template_id": tpl.id,
            "name": tpl.name,
            "original_filename": tpl.original_filename,
            "schema": schema,
            "message": "New template successfully registered in your library."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to parse template: {e}")
    finally:
        Path(path).unlink(missing_ok=True)

@router.post("/sources/upload")
async def upload_source(file: UploadFile = File(...)):
    path = await save_upload(file)
    try:
        questions = parse_source_document(path)
        stats = questions[0].get("extraction_stats") if questions and "extraction_stats" in questions[0] else {}
        return {
            "source_filename": file.filename,
            "source_type": Path(file.filename or "").suffix.lstrip("."),
            "questions": questions,
            "statistics": stats
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse source document: {e}")
    finally:
        Path(path).unlink(missing_ok=True)

@router.post("/validate-compatibility")
def check_compatibility(payload: dict = Body(...), db: Session = Depends(get_db)):
    template_id = payload.get("template_id")
    questions = payload.get("questions", [])
    
    tpl = db.get(Template, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
        
    schema = tpl.schema_json
    report = validate_compatibility(schema, questions)
    return report

@router.post("/ai-fill-fields")
def ai_fill_fields(payload: dict = Body(...)):
    from app.services.azure_openai import fill_missing_fields_for_questions
    questions = payload.get("questions", [])
    fields_to_fill = payload.get("fields", [])
    context = payload.get("context", {})

    if not questions or not fields_to_fill:
        return {"suggestions": []}

    try:
        suggestions = fill_missing_fields_for_questions(questions, fields_to_fill, context)
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Fill Fields failed: {e}")


@router.post("/questions/{question_id}/ai-fill")
def ai_fill_question_fields(question_id: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    """
    ONE-CLICK complete missing-field resolution for a single question.

    Flow:
    1. Load question + template schema from DB
    2. Dynamically compute ALL truly-missing fields (empty data_json values, excluding answer/core columns)
    3. Make ONE focused AI call to infer all missing fields simultaneously
    4. Validate AI response has an entry for every requested field
    5. Atomically persist all resolved fields (confidence >= threshold) in one db.commit()
    6. Re-run validation
    7. Return complete updated question object
    """
    import logging
    logger = logging.getLogger("ai_fill")

    from app.services.azure_openai import (
        fill_missing_fields_for_single_question,
        AI_FILL_CONFIDENCE_THRESHOLD,
    )

    # --- 1. Load question and template ---
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    qs = q.question_set
    if not qs or not qs.template:
        raise HTTPException(status_code=400, detail="Question has no valid template context")

    template_schema = qs.template.schema_json
    columns = template_schema.get("columns", [])
    column_schema = template_schema.get("column_schema", [])

    context = payload.get("context", {})

    # --- 2. Identify answer/core columns to protect ---
    # These are columns that should never be auto-filled: question, options, and answer-related fields
    answer_keywords = {"answer", "correct", "solution", "key", "option", "choice", "question", "prompt", "stem"}
    answer_cols = set()
    for col in columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in answer_keywords):
            answer_cols.add(col)

    # --- 3. Compute truly-missing fields (empty in data_json, not an answer column) ---
    data_json = dict(q.data_json or {})
    missing_fields = [
        col for col in columns
        if col not in answer_cols and not str(data_json.get(col, "") or "").strip()
    ]

    logger.info(
        "AI_FILL_START | question_id=%s | total_columns=%d | answer_cols=%s | missing_fields=%s",
        question_id,
        len(columns),
        list(answer_cols),
        missing_fields,
    )

    if not missing_fields:
        # Nothing to fill — return current question state
        logger.info("AI_FILL_COMPLETE | question_id=%s | no_missing_fields", question_id)
        return _build_question_response(q)

    # --- 4. Make ONE focused AI call ---
    try:
        fill_result = fill_missing_fields_for_single_question(
            question_data=data_json,
            missing_fields=missing_fields,
            template_schema=template_schema,
            context=context,
        )
    except Exception as e:
        logger.error("AI_FILL_ERROR | question_id=%s | error=%s", question_id, str(e))
        raise HTTPException(status_code=500, detail=f"AI fill failed: {e}")

    # --- 5. Persist all resolved fields atomically ---
    new_data = dict(data_json)
    new_metadata = dict(q.source_metadata_json or {"source_page": None, "fields": {}})
    if "fields" not in new_metadata:
        new_metadata["fields"] = {}

    resolved_fields = []
    unresolved_fields = []
    review_required_fields = []

    for field_name, field_result in fill_result.items():
        status = field_result.get("status", "UNRESOLVED")
        value = field_result.get("value")
        confidence = float(field_result.get("confidence", 0.0))
        reason = field_result.get("reason", "")

        if status == "AI_INFERRED" and value and confidence >= AI_FILL_CONFIDENCE_THRESHOLD:
            # Persist: update data and metadata
            new_data[field_name] = str(value)
            new_metadata["fields"][field_name] = {
                "origin": "inferred",
                "confidence": confidence,
                "reason": reason,
            }
            resolved_fields.append(field_name)
        elif status == "AI_INFERRED" and value and confidence < AI_FILL_CONFIDENCE_THRESHOLD:
            # Below threshold — flag for review but do NOT auto-persist
            new_metadata["fields"][field_name] = {
                "origin": "missing",
                "confidence": confidence,
                "ai_suggestion": value,
                "review_required": True,
                "reason": reason,
            }
            review_required_fields.append(field_name)
        else:
            # Truly unresolvable — leave data_json empty, update metadata
            new_metadata["fields"][field_name] = {
                "origin": "missing",
                "confidence": 0.0,
                "reason": reason or "Could not be safely inferred.",
            }
            unresolved_fields.append(field_name)

    logger.info(
        "AI_FILL_DATABASE_UPDATE | question_id=%s | resolved=%s | review_required=%s | unresolved=%s",
        question_id,
        resolved_fields,
        review_required_fields,
        unresolved_fields,
    )

    # --- 6. Re-run validation ---
    errors = validate_question_row(new_data, template_schema)
    existing_ai_val = q.validation_json.get("ai_validation") if q.validation_json else None
    val_status = {
        "valid": len(errors) == 0,
        "errors": errors,
        "ai_validation": existing_ai_val,
    }

    # --- 7. Atomic DB commit ---
    q.data_json = new_data
    q.source_metadata_json = new_metadata
    q.validation_json = val_status
    q.status = "VALIDATED" if val_status["valid"] else "INVALID"
    db.commit()
    db.refresh(q)

    logger.info(
        "AI_FILL_COMPLETE | question_id=%s | resolved_count=%d | unresolved_count=%d | review_required_count=%d",
        question_id,
        len(resolved_fields),
        len(unresolved_fields),
        len(review_required_fields),
    )

    return _build_question_response(q)



@router.post("/validate-answers")
def validate_answers(payload: dict = Body(...), db: Session = Depends(get_db)):
    from app.services.answer_validation_engine import validate_questions_batch_answers
    questions = payload.get("questions", [])
    subject = payload.get("subject", "General")
    context = payload.get("context", {})
    question_set_id = payload.get("question_set_id")

    if not questions:
        return {"results": []}

    try:
        results = validate_questions_batch_answers(questions, subject=subject, context=context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Answer Validation failed: {e}")

    # If question_set_id or DB questions match, update their validation_json in DB
    if question_set_id:
        for res in results:
            q_id = res.get("question_id")
            if q_id:
                q_db = db.get(Question, q_id)
                if q_db:
                    current_val = dict(q_db.validation_json or {})
                    current_val["ai_validation"] = res
                    if res.get("validation_status") == "ANSWER_CONFLICT":
                        current_val["valid"] = False
                        if "Answer conflict with AI solver" not in current_val.get("errors", []):
                            current_val.setdefault("errors", []).append("Answer conflict with AI solver")
                    q_db.validation_json = current_val
        db.commit()

    return {"results": results}

@router.post("/map")
def map_and_save(payload: dict = Body(...), db: Session = Depends(get_db)):
    import time
    import logging
    from fastapi.responses import StreamingResponse
    from app.services.azure_openai import map_fields_via_ai, fill_missing_fields_for_questions
    from app.services.answer_validation_engine import validate_single_question_answer
    from app.services.azure_openai import AI_FILL_CONFIDENCE_THRESHOLD
    from concurrent.futures import ThreadPoolExecutor

    # Start timing
    logger = logging.getLogger("ai_mapping")
    logger.info("MAP_START")
    start_time = time.perf_counter()

    template_id = payload.get("template_id")
    questions = payload.get("questions", [])
    source_filename = payload.get("source_filename", "")
    source_type = payload.get("source_type", "")
    subject = payload.get("subject", "General")
    context = payload.get("context", {})

    # 2. Template schema loading time (caching)
    template_load_start = time.perf_counter()
    global _TEMPLATE_SCHEMA_CACHE
    if template_id in _TEMPLATE_SCHEMA_CACHE:
        cached_schema = _TEMPLATE_SCHEMA_CACHE[template_id]
    else:
        tpl = db.get(Template, template_id)
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        cached_schema = {
            "id": tpl.id,
            "name": tpl.name,
            "schema_json": tpl.schema_json,
            "columns": tpl.schema_json.get("columns", []),
            "column_schema": [
                {
                    "original_name": c.get("original_name"),
                    "normalized_name": c.get("normalized_name"),
                    "required": c.get("required"),
                    "example_value": c.get("example_value")
                }
                for c in tpl.schema_json.get("column_schema", [])
            ]
        }
        _TEMPLATE_SCHEMA_CACHE[template_id] = cached_schema
        
    template_load_time = time.perf_counter() - template_load_start

    # 15. Avoid Duplicate Processing
    existing_qs = db.query(QuestionSet).filter_by(
        template_id=template_id,
        source_filename=source_filename,
        source_type=source_type,
        status="MAPPED"
    ).order_by(QuestionSet.id.desc()).first()
    
    if existing_qs and len(existing_qs.questions) == len(questions):
        logger.info("REUSING_EXISTING_MAPPING | question_set_id=%s", existing_qs.id)
        def generate_reused_steps():
            yield json.dumps({"type": "progress", "message": "✓ Reusing existing mapping result..."}) + "\n"
            
            response_payload = {
                "question_set_id": existing_qs.id,
                "template_name": cached_schema["name"],
                "columns": cached_schema["columns"],
                "questions": [
                    {
                        "id": q.id,
                        "row_number": q.row_number,
                        "data_json": q.data_json,
                        "validation": q.validation_json,
                        "source_metadata": q.source_metadata_json,
                        "status": q.status,
                        "source_answer": q.validation_json.get("ai_validation", {}).get("source_answer") if q.validation_json else None,
                        "ai_answer": q.validation_json.get("ai_validation", {}).get("ai_answer") if q.validation_json else None,
                        "final_answer": q.data_json.get("Correct Answer") or q.data_json.get("correct_answer"),
                        "answer_source": q.source_metadata_json.get("answer_source") if q.source_metadata_json else "EXPLICIT_ANSWER_KEY",
                        "answer_page": q.source_metadata_json.get("answer_page") if q.source_metadata_json else None,
                        "answer_section": q.source_metadata_json.get("answer_section") if q.source_metadata_json else None,
                        "mapping_confidence": q.source_metadata_json.get("mapping_confidence") if q.source_metadata_json else 0.95,
                        "answer_mapping_status": q.source_metadata_json.get("answer_mapping_status") if q.source_metadata_json else "ANSWER_MAPPED",
                        "mapping_reason": q.source_metadata_json.get("mapping_reason") if q.source_metadata_json else None
                    }
                    for q in sorted(existing_qs.questions, key=lambda x: x.row_number)
                ]
            }
            yield json.dumps({"type": "result", "data": response_payload}) + "\n"
            
        return StreamingResponse(generate_reused_steps(), media_type="application/x-ndjson")

    def generate_mapping_steps():
        nonlocal start_time
        
        # 1. Source loading time (already in payload)
        source_load_start = time.perf_counter()
        source_load_time = time.perf_counter() - source_load_start
        logger.info("SOURCE_LOAD_TIME | duration=%.4f", source_load_time)

        # 2. Template schema loading time (logged)
        logger.info("TEMPLATE_LOAD_TIME | duration=%.4f", template_load_time)

        yield json.dumps({"type": "progress", "message": "Mapping source fields..."}) + "\n"

        # 3. Deterministic Mapping
        deterministic_start = time.perf_counter()
        
        target_columns = cached_schema["columns"]
        column_schema = cached_schema["column_schema"]
        
        # Get all unique source keys
        source_keys = sorted(list(set(k for q in questions for k in q.keys() if k not in ("id", "row_number", "source_page"))))
        
        def clean_key(name: str) -> str:
            return "".join(c for c in name.lower() if c.isalnum())

        cleaned_source = {clean_key(sk): sk for sk in source_keys}
        
        mapping_result = {}
        mapped_source_keys = set()
        unmapped_target_cols = []
        
        aliases = {
            "problemstatement": ["question", "questiontext", "prompt", "stem"],
            "question": ["problemstatement", "questiontext", "prompt", "stem"],
            "correctanswer": ["answer", "correctoption", "key"],
            "answer": ["correctanswer", "correctoption", "key"],
            "difficulty": ["difficultylevel", "level"],
            "score": ["marks", "mark", "points"],
            "optiona": ["option1", "answer1", "choicea", "choice1"],
            "optionb": ["option2", "answer2", "choiceb", "choice2"],
            "optionc": ["option3", "answer3", "choicec", "choice3"],
            "optiond": ["option4", "answer4", "choiced", "choice4"],
            "option1": ["optiona", "choicea", "choice1", "answer1"],
            "option2": ["optionb", "choiceb", "choice2", "answer2"],
            "option3": ["optionc", "choicec", "choice3", "answer3"],
            "option4": ["optiond", "choiced", "choice4", "answer4"],
        }
        
        for col in target_columns:
            col_clean = clean_key(col)
            
            # Exact match
            exact_match = None
            for sk in source_keys:
                if sk.lower() == col.lower():
                    exact_match = sk
                    break
            if exact_match:
                mapping_result[col] = {
                    "source_field": exact_match,
                    "origin": "extracted",
                    "confidence": 1.0
                }
                mapped_source_keys.add(exact_match)
                continue
                
            # Cleaned match
            if col_clean in cleaned_source:
                sk = cleaned_source[col_clean]
                mapping_result[col] = {
                    "source_field": sk,
                    "origin": "extracted",
                    "confidence": 1.0
                }
                mapped_source_keys.add(sk)
                continue
                
            # Alias match
            found_alias = None
            if col_clean in aliases:
                for alias in aliases[col_clean]:
                    if alias in cleaned_source:
                        sk = cleaned_source[alias]
                        found_alias = sk
                        break
            if found_alias:
                mapping_result[col] = {
                    "source_field": found_alias,
                    "origin": "extracted",
                    "confidence": 0.95
                }
                mapped_source_keys.add(found_alias)
                continue
                
            unmapped_target_cols.append(col)
            
        deterministic_time = time.perf_counter() - deterministic_start
        logger.info("DETERMINISTIC_MAPPING_TIME | duration=%.4f", deterministic_time)
        
        matched_count = len(mapping_result)
        yield json.dumps({"type": "progress", "message": f"✓ Matched {matched_count} fields"}) + "\n"

        # 4. AI Semantic Mapping for Ambiguous Fields
        ai_mapping_start = time.perf_counter()
        remaining_source = [sk for sk in source_keys if sk not in mapped_source_keys]
        
        ai_mapping_count = 0
        if unmapped_target_cols and remaining_source:
            ai_mappings = map_fields_via_ai(
                source_fields=remaining_source,
                target_fields=unmapped_target_cols,
                context=context
            )
            for target, map_info in ai_mappings.items():
                source = map_info.get("source")
                confidence = map_info.get("confidence", 0.8)
                if source in remaining_source:
                    mapping_result[target] = {
                        "source_field": source,
                        "origin": "extracted",
                        "confidence": confidence
                    }
                    mapped_source_keys.add(source)
                    ai_mapping_count += 1
                    if target in unmapped_target_cols:
                        unmapped_target_cols.remove(target)

        # Mark truly unmapped/missing columns
        for col in unmapped_target_cols:
            mapping_result[col] = {
                "source_field": None,
                "origin": "missing",
                "confidence": 0.0
            }
            
        ai_mapping_time = time.perf_counter() - ai_mapping_start
        logger.info("AI_MAPPING_TIME | duration=%.4f", ai_mapping_time)
        
        if ai_mapping_count > 0:
            yield json.dumps({"type": "progress", "message": f"✓ Resolved {ai_mapping_count} semantic mappings"}) + "\n"

        # 5. Apply Global Mapping & Distribute Options
        mapped_questions = []
        opt_cols = []
        for col in target_columns:
            col_clean = clean_key(col)
            if col_clean in ("optiona", "option1", "choicea", "choice1", "answer1"):
                opt_cols.append((0, col))
            elif col_clean in ("optionb", "option2", "choiceb", "choice2", "answer2"):
                opt_cols.append((1, col))
            elif col_clean in ("optionc", "option3", "choicec", "choice3", "answer3"):
                opt_cols.append((2, col))
            elif col_clean in ("optiond", "option4", "choiced", "choice4", "answer4"):
                opt_cols.append((3, col))
                
        for idx, q in enumerate(questions, start=1):
            data = {}
            metadata = {}
            source_page = q.get("source_page")
            
            options_list = q.get("options") or []
            if not isinstance(options_list, list):
                options_list = []
                
            for col in target_columns:
                map_info = mapping_result[col]
                source_field = map_info.get("source_field")
                origin = map_info.get("origin", "missing")
                confidence = map_info.get("confidence", 0.0)
                
                value = ""
                if source_field and source_field in q:
                    val = q[source_field]
                    if isinstance(val, list):
                        value = ", ".join(str(v) for v in val)
                    else:
                        value = str(val or "")
                else:
                    matched_opt_idx = next((opt_idx for opt_idx, ocol in opt_cols if ocol == col), None)
                    if matched_opt_idx is not None and matched_opt_idx < len(options_list):
                        value = str(options_list[matched_opt_idx] or "")
                        origin = "extracted"
                        confidence = 1.0
                        
                data[col] = value.strip()
                metadata[col] = {
                    "origin": origin,
                    "confidence": confidence
                }
                
            mapped_questions.append({
                "data": data,
                "metadata": metadata,
                "source_page": source_page
            })
            
        yield json.dumps({"type": "progress", "message": f"✓ Applied mapping to {len(questions)} questions"}) + "\n"

        # 6. Identify Missing/Inferable Fields & Run Batch AI Inference
        inferable_columns = []
        for col in target_columns:
            norm = normalize_field_name(col)
            if norm in {"topic", "subtopic", "difficulty", "score", "blooms_taxonomy", "bloom's taxonomy", "cognitive_level"}:
                if any(not mq["data"].get(col) for mq in mapped_questions):
                    inferable_columns.append(col)
                    
        if inferable_columns:
            questions_for_ai = []
            for idx, mq in enumerate(mapped_questions, start=1):
                q_data = dict(mq["data"])
                q_data["question_id"] = f"q_{idx}"
                questions_for_ai.append(q_data)
                
            try:
                suggestions = fill_missing_fields_for_questions(questions_for_ai, inferable_columns, context)
                suggestions_by_id = {s.get("question_id"): s.get("fields", {}) for s in suggestions if s.get("question_id")}
                
                for idx, mq in enumerate(mapped_questions, start=1):
                    q_id = f"q_{idx}"
                    if q_id in suggestions_by_id:
                        s_fields = suggestions_by_id[q_id]
                        for col in inferable_columns:
                            if col in s_fields and not mq["data"].get(col):
                                s_info = s_fields[col]
                                status = s_info.get("status", "UNRESOLVED")
                                val = s_info.get("value")
                                conf = float(s_info.get("confidence", 0.0))
                                
                                if status == "AI_INFERRED" and val and conf >= AI_FILL_CONFIDENCE_THRESHOLD:
                                    mq["data"][col] = str(val)
                                    mq["metadata"][col] = {
                                        "origin": "inferred",
                                        "confidence": conf,
                                        "reason": s_info.get("reason", "")
                                    }
                                else:
                                    mq["metadata"][col] = {
                                        "origin": "missing",
                                        "confidence": conf,
                                        "review_required": True,
                                        "ai_suggestion": val,
                                        "reason": s_info.get("reason", "")
                                    }
            except Exception as e:
                logger.error("AI_MAPPING_INFERENCE_ERROR | error=%s", str(e))

        yield json.dumps({"type": "progress", "message": "✓ Validating mapped fields..."}) + "\n"

        # 7. Parallelize Validation
        validation_start = time.perf_counter()
        
        schema = cached_schema["schema_json"]

        def validate_question_thread(idx_and_mq):
            idx, mq = idx_and_mq
            row_data = mq.get("data", {})
            meta_data = mq.get("metadata", {})
            source_page = mq.get("source_page")
            
            orig_q = questions[idx - 1] if idx - 1 < len(questions) else {}
            answer_source = orig_q.get("answer_source", "EXPLICIT_ANSWER_KEY" if orig_q.get("correct_answer") else "MISSING")
            answer_page = orig_q.get("answer_page")
            answer_section = orig_q.get("answer_section", "Answer Key")
            mapping_confidence = orig_q.get("mapping_confidence", 0.95 if orig_q.get("correct_answer") else 0.0)
            mapping_status = orig_q.get("answer_mapping_status", "ANSWER_MAPPED" if orig_q.get("correct_answer") else "MISSING_ANSWER")
            mapping_reason = orig_q.get("mapping_reason", "Extracted from source.")

            normalized_row_data = {}
            for col in target_columns:
                normalized_row_data[col] = str(row_data.get(col, "") or "").strip()
                
            errors = validate_question_row(normalized_row_data, schema)
            
            source_metadata = {
                "source_page": source_page,
                "answer_source": answer_source,
                "answer_page": answer_page,
                "answer_section": answer_section,
                "mapping_confidence": mapping_confidence,
                "answer_mapping_status": mapping_status,
                "mapping_reason": mapping_reason,
                "fields": {}
            }
            for col in target_columns:
                col_meta = meta_data.get(col, {})
                source_metadata["fields"][col] = {
                    "origin": col_meta.get("origin", "missing"),
                    "confidence": col_meta.get("confidence", 0.0)
                }
                if col_meta.get("review_required"):
                    source_metadata["fields"][col]["review_required"] = True
                if col_meta.get("ai_suggestion"):
                    source_metadata["fields"][col]["ai_suggestion"] = col_meta.get("ai_suggestion")
                if col_meta.get("reason"):
                    source_metadata["fields"][col]["reason"] = col_meta.get("reason")
                
            val_input = {
                "id": f"q_{idx}",
                "row_number": idx,
                "source_metadata": source_metadata,
                **normalized_row_data
            }
            ai_val = validate_single_question_answer(val_input, subject=subject, context=context)

            if ai_val.get("validation_status") == "ANSWER_CONFLICT":
                errors.append(f"Answer Conflict: Source answer ({ai_val.get('source_answer')}) differs from AI validated answer ({ai_val.get('ai_answer')})")

            val_status = {
                "valid": len(errors) == 0,
                "errors": errors,
                "ai_validation": ai_val
            }
            
            return idx, normalized_row_data, val_status, source_metadata

        # Execute concurrently
        with ThreadPoolExecutor(max_workers=min(16, len(mapped_questions))) as executor:
            thread_results = list(executor.map(validate_question_thread, enumerate(mapped_questions, start=1)))
            
        validation_time = time.perf_counter() - validation_start
        logger.info("VALIDATION_TIME | duration=%.4f", validation_time)

        # 8. Batch Database Writes
        db_write_start = time.perf_counter()
        
        # Save QuestionSet
        qs = QuestionSet(
            template_id=template_id,
            source_filename=source_filename,
            source_type=source_type,
            status="MAPPED"
        )
        db.add(qs)
        db.flush()
        
        saved_questions = []
        thread_results.sort(key=lambda x: x[0])
        for idx, normalized_row_data, val_status, source_metadata in thread_results:
            q_item = Question(
                question_set_id=qs.id,
                row_number=idx,
                data_json=normalized_row_data,
                validation_json=val_status,
                source_metadata_json=source_metadata,
                status="VALIDATED" if val_status["valid"] else "INVALID"
            )
            saved_questions.append(q_item)
            
        db.add_all(saved_questions)
        db.commit()
        
        # Refresh to get IDs
        for q in saved_questions:
            db.refresh(q)
            
        db_write_time = time.perf_counter() - db_write_start
        logger.info("DATABASE_WRITE_TIME | duration=%.4f", db_write_time)

        # 9. Response Serialization & Total Time
        resp_serialization_start = time.perf_counter()
        
        response_payload = {
            "question_set_id": qs.id,
            "template_name": cached_schema["name"],
            "columns": target_columns,
            "questions": [
                {
                    "id": q.id,
                    "row_number": q.row_number,
                    "data_json": q.data_json,
                    "validation": q.validation_json,
                    "source_metadata": q.source_metadata_json,
                    "status": q.status,
                    "source_answer": q.validation_json.get("ai_validation", {}).get("source_answer") if q.validation_json else None,
                    "ai_answer": q.validation_json.get("ai_validation", {}).get("ai_answer") if q.validation_json else None,
                    "final_answer": q.data_json.get("Correct Answer") or q.data_json.get("correct_answer"),
                    "answer_source": q.source_metadata_json.get("answer_source") if q.source_metadata_json else "EXPLICIT_ANSWER_KEY",
                    "answer_page": q.source_metadata_json.get("answer_page") if q.source_metadata_json else None,
                    "answer_section": q.source_metadata_json.get("answer_section") if q.source_metadata_json else None,
                    "mapping_confidence": q.source_metadata_json.get("mapping_confidence") if q.source_metadata_json else 0.95,
                    "answer_mapping_status": q.source_metadata_json.get("answer_mapping_status") if q.source_metadata_json else "ANSWER_MAPPED",
                    "mapping_reason": q.source_metadata_json.get("mapping_reason") if q.source_metadata_json else None
                }
                for q in saved_questions
            ]
        }
        
        resp_serialization_time = time.perf_counter() - resp_serialization_start
        logger.info("RESPONSE_SERIALIZATION_TIME | duration=%.4f", resp_serialization_time)

        total_time = time.perf_counter() - start_time
        logger.info("MAP_TOTAL_TIME | duration=%.4f", total_time)

        yield json.dumps({"type": "result", "data": response_payload}) + "\n"

    return StreamingResponse(generate_mapping_steps(), media_type="application/x-ndjson")

@router.get("/question-sets")
def list_question_sets(db: Session = Depends(get_db)):
    sets = db.query(QuestionSet).order_by(QuestionSet.created_at.desc()).all()
    return [
        {
            "id": s.id,
            "template_name": s.template.name if s.template else "No Template",
            "source_filename": s.source_filename,
            "source_type": s.source_type,
            "status": s.status,
            "created_at": s.created_at.isoformat()
        }
        for s in sets
    ]

@router.get("/question-sets/{set_id}")
def get_question_set(set_id: str, db: Session = Depends(get_db)):
    qs = db.get(QuestionSet, set_id)
    if not qs:
        raise HTTPException(status_code=404, detail="Question set not found")
        
    tpl = qs.template
    if not tpl:
        raise HTTPException(status_code=404, detail="Template associated with this question set not found")
        
    questions = sorted(qs.questions, key=lambda x: x.row_number or 0)
    
    return {
        "id": qs.id,
        "template_id": tpl.id,
        "template_name": tpl.name,
        "source_filename": qs.source_filename,
        "columns": tpl.schema_json.get("columns", []),
        "questions": [
            {
                "id": q.id,
                "row_number": q.row_number,
                "data_json": q.data_json,
                "validation": q.validation_json,
                "source_metadata": q.source_metadata_json,
                "status": q.status,
                "source_answer": q.validation_json.get("ai_validation", {}).get("source_answer") if q.validation_json else None,
                "ai_answer": q.validation_json.get("ai_validation", {}).get("ai_answer") if q.validation_json else None,
                "final_answer": q.data_json.get("Correct Answer") or q.data_json.get("correct_answer"),
                "answer_source": q.source_metadata_json.get("answer_source") if q.source_metadata_json else "EXPLICIT_ANSWER_KEY",
                "answer_page": q.source_metadata_json.get("answer_page") if q.source_metadata_json else None,
                "answer_section": q.source_metadata_json.get("answer_section") if q.source_metadata_json else None,
                "mapping_confidence": q.source_metadata_json.get("mapping_confidence") if q.source_metadata_json else 0.95,
                "answer_mapping_status": q.source_metadata_json.get("answer_mapping_status") if q.source_metadata_json else "ANSWER_MAPPED",
                "mapping_reason": q.source_metadata_json.get("mapping_reason") if q.source_metadata_json else None
            }
            for q in questions
        ]
    }

@router.patch("/questions/{question_id}")
def update_question(question_id: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
        
    qs = q.question_set
    if not qs or not qs.template:
        raise HTTPException(status_code=400, detail="Question has no valid template context")
        
    schema = qs.template.schema_json
    
    new_data = dict(q.data_json)
    new_metadata = dict(q.source_metadata_json or {"source_page": None, "fields": {}})
    if "fields" not in new_metadata:
        new_metadata["fields"] = {}
        
    for k, v in payload.items():
        new_data[k] = v
        new_metadata["fields"][k] = {
            "origin": "user_edited",
            "confidence": 1.0
        }
        
    errors = validate_question_row(new_data, schema)
    existing_ai_val = q.validation_json.get("ai_validation") if q.validation_json else None
    
    val_status = {
        "valid": len(errors) == 0,
        "errors": errors,
        "ai_validation": existing_ai_val
    }
    
    q.data_json = new_data
    q.validation_json = val_status
    q.source_metadata_json = new_metadata
    q.status = "VALIDATED" if val_status["valid"] else "INVALID"
    
    db.commit()
    db.refresh(q)
    
    return {
        "id": q.id,
        "row_number": q.row_number,
        "data_json": q.data_json,
        "validation": q.validation_json,
        "source_metadata": q.source_metadata_json,
        "status": q.status,
        "source_answer": q.validation_json.get("ai_validation", {}).get("source_answer") if q.validation_json else None,
        "ai_answer": q.validation_json.get("ai_validation", {}).get("ai_answer") if q.validation_json else None,
        "final_answer": q.data_json.get("Correct Answer") or q.data_json.get("correct_answer"),
        "answer_source": q.source_metadata_json.get("answer_source") if q.source_metadata_json else "EXPLICIT_ANSWER_KEY",
        "answer_page": q.source_metadata_json.get("answer_page") if q.source_metadata_json else None,
        "answer_section": q.source_metadata_json.get("answer_section") if q.source_metadata_json else None,
        "mapping_confidence": q.source_metadata_json.get("mapping_confidence") if q.source_metadata_json else 0.95,
        "answer_mapping_status": q.source_metadata_json.get("answer_mapping_status") if q.source_metadata_json else "ANSWER_MAPPED",
        "mapping_reason": q.source_metadata_json.get("mapping_reason") if q.source_metadata_json else None
    }


