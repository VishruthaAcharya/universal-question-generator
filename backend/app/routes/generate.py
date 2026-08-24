import os
import json
import hashlib
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

def compute_schema_fingerprint(schema: dict) -> str:
    canonical = {
        "columns": schema.get("columns", []),
        "column_schema": [
            {
                "original_name": c.get("original_name"),
                "normalized_name": c.get("normalized_name"),
                "required": c.get("required")
            }
            for c in sorted(schema.get("column_schema", []), key=lambda x: x.get("original_name", ""))
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
        return {
            "source_filename": file.filename,
            "source_type": Path(file.filename or "").suffix.lstrip("."),
            "questions": questions
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

@router.post("/map")
def map_and_save(payload: dict = Body(...), db: Session = Depends(get_db)):
    template_id = payload.get("template_id")
    questions = payload.get("questions", [])
    source_filename = payload.get("source_filename", "")
    source_type = payload.get("source_type", "")
    
    tpl = db.get(Template, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
        
    schema = tpl.schema_json
    columns = schema.get("columns", [])
    
    from app.services.azure_openai import infer_missing_fields_and_map
    try:
        mapped_questions_info = infer_missing_fields_and_map(questions, schema)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI mapping service error: {e}")

    # Save QuestionSet
    qs = QuestionSet(
        template_id=tpl.id,
        source_filename=source_filename,
        source_type=source_type,
        status="MAPPED"
    )
    db.add(qs)
    db.flush()
    
    saved_questions = []
    for idx, mq in enumerate(mapped_questions_info, start=1):
        row_data = mq.get("data", {})
        meta_data = mq.get("metadata", {})
        source_page = mq.get("source_page")
        
        normalized_row_data = {}
        for col in columns:
            normalized_row_data[col] = str(row_data.get(col, "") or "").strip()
            
        errors = validate_question_row(normalized_row_data, schema)
        val_status = {
            "valid": len(errors) == 0,
            "errors": errors
        }
        
        source_metadata = {
            "source_page": source_page,
            "fields": {}
        }
        for col in columns:
            col_meta = meta_data.get(col, {})
            source_metadata["fields"][col] = {
                "origin": col_meta.get("origin", "missing"),
                "confidence": col_meta.get("confidence", 0.0)
            }
            
        q_item = Question(
            question_set_id=qs.id,
            row_number=idx,
            data_json=normalized_row_data,
            validation_json=val_status,
            source_metadata_json=source_metadata,
            status="VALIDATED" if val_status["valid"] else "INVALID"
        )
        db.add(q_item)
        saved_questions.append(q_item)
        
    db.commit()
    
    return {
        "question_set_id": qs.id,
        "template_name": tpl.name,
        "columns": columns,
        "questions": [
            {
                "id": q.id,
                "row_number": q.row_number,
                "data_json": q.data_json,
                "validation": q.validation_json,
                "source_metadata": q.source_metadata_json,
                "status": q.status
            }
            for q in saved_questions
        ]
    }

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
                "status": q.status
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
    val_status = {
        "valid": len(errors) == 0,
        "errors": errors
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
        "status": q.status
    }
