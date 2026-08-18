import json
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse
from app.services.exporter import export_csv, export_xlsx
from app.services.validator import validate_questions

router = APIRouter(prefix="/api", tags=["export"])

@router.post("/validate")
async def validate(payload: dict = Body(...)):
    questions = payload.get("questions", [])
    return {"validation": validate_questions(questions)}

@router.post("/export")
async def export(payload: dict = Body(...)):
    questions = payload.get("questions", [])
    columns = payload.get("columns", [])
    fmt = payload.get("format", "xlsx")
    if not questions or not columns:
        raise HTTPException(400, "Questions and columns are required.")

    validation = validate_questions(questions)
    invalid = [r for r in validation if not r["valid"]]
    if invalid:
        raise HTTPException(400, {"message": "Fix validation errors before export.", "validation": validation})

    if fmt == "csv":
        buf = export_csv(questions, columns)
        return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="questions_generated.csv"'})
    if fmt == "xlsx":
        buf = export_xlsx(questions, columns)
        return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="questions_generated.xlsx"'})
    raise HTTPException(400, "Format must be csv or xlsx.")
