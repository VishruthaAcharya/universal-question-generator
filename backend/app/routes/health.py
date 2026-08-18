from fastapi import APIRouter
from sqlalchemy import text
from app.database import SessionLocal
router=APIRouter(tags=["health"])
@router.get("/health")
def health(): return {"status":"ok"}
@router.get("/health/ready")
def ready():
    try:
        with SessionLocal() as db: db.execute(text("SELECT 1"))
        return {"status":"ready","database":"ok"}
    except Exception: return {"status":"not_ready","database":"error"}
