import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import QuestionSet, Question
from app.services.source_reader import read_source
from app.services.template import read_template
from app.services.ai import generate_questions
from app.services.validator import validate_questions

router=APIRouter(prefix="/api",tags=["generation"])

async def save_upload(upload: UploadFile):
    fd,path=tempfile.mkstemp(suffix=Path(upload.filename or "").suffix)
    Path(path).write_bytes(await upload.read()); return path

def qdict(q):
    return {"id":q.id,"question_set_id":q.question_set_id,"question":q.question,"topic":q.topic,"subtopic":q.subtopic,
            "answer_1":q.answer_1,"answer_2":q.answer_2,"answer_3":q.answer_3,"answer_4":q.answer_4,
            "difficulty":q.difficulty,"correct_answer":q.correct_answer,"score":q.score,"source_page":q.source_page,"status":q.status}

@router.post("/generate")
async def generate(template:UploadFile=File(...),source:UploadFile=File(...),subject:str=Form(""),name:str=Form("Generated Question Set"),
                   difficulty:str=Form("Auto"),score:int=Form(1),question_count:int=Form(5),db:Session=Depends(get_db)):
    tp=await save_upload(template); sp=await save_upload(source)
    try:
        columns=read_template(tp); text=read_source(sp)
        qs=generate_questions(text,max(1,min(question_count,100)))
        for q in qs:
            q["score"]=score
            if difficulty in {"Easy","Medium","Hard"}: q["difficulty"]=difficulty
        validation=validate_questions(qs)
        if any(not x["valid"] for x in validation): raise HTTPException(422,{"message":"Invalid generated questions","validation":validation})
        batch=QuestionSet(name=name,subject=subject,source_file=source.filename or "",generation_mode="CET_MCQ")
        db.add(batch); db.flush()
        saved=[]
        for q in qs:
            item=Question(question_set_id=batch.id,question=q["question"],topic=q.get("topic",""),subtopic=q.get("subtopic",""),
                answer_1=q["answer_1"],answer_2=q["answer_2"],answer_3=q["answer_3"],answer_4=q["answer_4"],
                difficulty=q["difficulty"],correct_answer=q["correct_answer"],score=q["score"],source_page=q.get("source_page"),status="GENERATED")
            db.add(item); saved.append(item)
        db.commit()
        return {"question_set_id":batch.id,"columns":columns,"questions":[qdict(q) for q in saved],"validation":validation}
    except HTTPException: db.rollback(); raise
    except Exception as e: db.rollback(); raise HTTPException(500,f"Generation failed: {e}")
    finally:
        Path(tp).unlink(missing_ok=True); Path(sp).unlink(missing_ok=True)

@router.get("/question-sets")
def list_sets(db:Session=Depends(get_db)):
    return [{"id":x.id,"name":x.name,"subject":x.subject,"source_file":x.source_file,"created_at":x.created_at.isoformat()} for x in db.query(QuestionSet).order_by(QuestionSet.created_at.desc()).all()]

@router.get("/question-sets/{set_id}")
def get_set(set_id:str,db:Session=Depends(get_db)):
    x=db.get(QuestionSet,set_id)
    if not x: raise HTTPException(404,"Question set not found")
    return {"id":x.id,"name":x.name,"subject":x.subject,"source_file":x.source_file,"questions":[qdict(q) for q in x.questions]}

@router.patch("/questions/{question_id}")
def update_question(question_id:str,payload:dict,db:Session=Depends(get_db)):
    q=db.get(Question,question_id)
    if not q: raise HTTPException(404,"Question not found")
    for field in ["question","topic","subtopic","answer_1","answer_2","answer_3","answer_4","difficulty","correct_answer","score","status"]:
        if field in payload: setattr(q,field,payload[field])
    errors=validate_questions([qdict(q)])[0]["errors"]
    if errors: db.rollback(); raise HTTPException(422,{"errors":errors})
    q.status="REVIEWED"; db.commit(); db.refresh(q); return qdict(q)
