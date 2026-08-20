from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pathlib import Path
from app.database import get_db
from app.models.models import QuestionSet, Template
from app.services.exporter import export_to_csv, export_to_xlsx

router = APIRouter(prefix="/api", tags=["export"])

STORAGE_DIR = Path("storage/templates")

@router.post("/export")
async def export_questions(payload: dict = Body(...), db: Session = Depends(get_db)):
    question_set_id = payload.get("question_set_id")
    fmt = payload.get("format", "xlsx").lower()
    
    if not question_set_id:
        raise HTTPException(status_code=400, detail="question_set_id is required.")
        
    qs = db.get(QuestionSet, question_set_id)
    if not qs:
        raise HTTPException(status_code=404, detail="Question set not found.")
        
    tpl = qs.template
    if not tpl:
        raise HTTPException(status_code=404, detail="Template associated with the question set not found.")
        
    columns = tpl.schema_json.get("columns", [])
    questions_list = [q.data_json for q in sorted(qs.questions, key=lambda x: x.row_number or 0)]
    
    # Locate original template file
    orig_suffix = Path(tpl.original_filename or "").suffix
    template_path = STORAGE_DIR / f"{tpl.id}{orig_suffix}"
    
    if fmt == "csv":
        buf = export_to_csv(questions_list, columns)
        filename = f"exported_{tpl.name}.csv"
        media_type = "text/csv"
    elif fmt == "xlsx":
        buf = export_to_xlsx(questions_list, columns, template_path=str(template_path), sheet_name=tpl.sheet_name)
        filename = f"exported_{tpl.name}.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        raise HTTPException(status_code=400, detail="Format must be csv or xlsx.")
        
    return StreamingResponse(
        buf,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
