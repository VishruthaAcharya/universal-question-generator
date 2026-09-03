import json
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db
from app.models import Template, QuestionSet, Question
from app.services.azure_openai import fill_missing_fields_for_single_question

# Setup in-memory SQLite database for testing
@pytest.fixture(name="db_session")
def db_session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with SessionLocal() as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(db_session: Session):
    def get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = get_db_override
    yield TestClient(app)
    app.dependency_overrides.clear()

def setup_template_and_qset(session: Session):
    tmpl = Template(
        name="Standard 10-Field Template",
        schema_json={
            "columns": [
                "Question Prompt", "Option A", "Option B", "Option C", "Option D",
                "Correct Answer", "Topic", "Subtopic", "Difficulty", "Marks",
                "Bloom Taxonomy", "Target Audience", "Explanation", "Tags"
            ],
            "column_schema": [
                {"original_name": "Question Prompt", "required": True},
                {"original_name": "Option A", "required": True},
                {"original_name": "Option B", "required": True},
                {"original_name": "Option C", "required": True},
                {"original_name": "Option D", "required": True},
                {"original_name": "Correct Answer", "required": True},
                {"original_name": "Topic", "required": False},
                {"original_name": "Subtopic", "required": False},
                {"original_name": "Difficulty", "required": False},
                {"original_name": "Marks", "required": False},
                {"original_name": "Bloom Taxonomy", "required": False},
                {"original_name": "Target Audience", "required": False},
                {"original_name": "Explanation", "required": False},
                {"original_name": "Tags", "required": False},
            ]
        }
    )
    session.add(tmpl)
    session.commit()
    session.refresh(tmpl)

    qset = QuestionSet(
        template_id=tmpl.id,
        source_filename="test_source.pdf",
        source_type="pdf",
        status="MAPPED"
    )
    session.add(qset)
    session.commit()
    session.refresh(qset)
    return tmpl, qset

# 1. Test Question with 1 Missing Field
def test_ai_fill_one_missing_field(client: TestClient, db_session: Session):
    tmpl, qset = setup_template_and_qset(db_session)
    q = Question(
        question_set_id=qset.id,
        row_number=1,
        data_json={
            "Question Prompt": "What is the capital of France?",
            "Option A": "London", "Option B": "Paris", "Option C": "Berlin", "Option D": "Rome",
            "Correct Answer": "B",
            "Topic": "Geography", "Subtopic": "Capitals", "Difficulty": "", # Only 1 missing
            "Marks": "1", "Bloom Taxonomy": "Recall", "Target Audience": "Grade 6", "Explanation": "Paris is capital", "Tags": "World"
        },
        source_metadata_json={"fields": {}},
        validation_json={"valid": True, "errors": []}
    )
    db_session.add(q)
    db_session.commit()
    db_session.refresh(q)

    mock_ai_response = {
        "Difficulty": {
            "value": "Easy",
            "status": "AI_INFERRED",
            "confidence": 0.95,
            "reason": "Standard world capital question"
        }
    }

    with patch("app.services.azure_openai.fill_missing_fields_for_single_question", return_value=mock_ai_response):
        res = client.post(f"/api/questions/{q.id}/ai-fill", json={"context": {"subject": "Geography"}})
        print("\n--- RES STATUS ---", res.status_code)
        print("--- RES JSON ---", res.json())
        assert res.status_code == 200
        data = res.json()
        assert data["data_json"]["Difficulty"] == "Easy"
        assert data["ai_fill_result"]["resolved_count"] == 1
        assert data["ai_fill_result"]["unresolved_count"] == 0
        assert data["source_metadata"]["fields"]["Difficulty"]["confidence"] == 0.95

# 2. Test Question with 3 Missing Fields
def test_ai_fill_three_missing_fields(client: TestClient, db_session: Session):
    tmpl, qset = setup_template_and_qset(db_session)
    q = Question(
        question_set_id=qset.id,
        row_number=2,
        data_json={
            "Question Prompt": "Solve for x: 2x + 6 = 14",
            "Option A": "3", "Option B": "4", "Option C": "5", "Option D": "6",
            "Correct Answer": "B",
            "Topic": "", "Subtopic": "", "Difficulty": "", # 3 missing
            "Marks": "2", "Bloom Taxonomy": "Apply", "Target Audience": "Grade 8", "Explanation": "2x=8 => x=4", "Tags": "Algebra"
        },
        source_metadata_json={"fields": {}},
        validation_json={"valid": True, "errors": []}
    )
    db_session.add(q)
    db_session.commit()
    db_session.refresh(q)

    mock_ai_response = {
        "Topic": {"value": "Algebra", "status": "AI_INFERRED", "confidence": 0.98, "reason": "Linear equation"},
        "Subtopic": {"value": "Linear Equations", "status": "AI_INFERRED", "confidence": 0.94, "reason": "One variable"},
        "Difficulty": {"value": "Easy", "status": "AI_INFERRED", "confidence": 0.90, "reason": "Basic arithmetic operations"}
    }

    with patch("app.services.azure_openai.fill_missing_fields_for_single_question", return_value=mock_ai_response):
        res = client.post(f"/api/questions/{q.id}/ai-fill", json={"context": {"subject": "Mathematics"}})
        assert res.status_code == 200
        data = res.json()
        assert data["data_json"]["Topic"] == "Algebra"
        assert data["data_json"]["Subtopic"] == "Linear Equations"
        assert data["data_json"]["Difficulty"] == "Easy"
        assert data["ai_fill_result"]["resolved_count"] == 3
        assert data["ai_fill_result"]["unresolved_count"] == 0

# 3. Test Question with 8+ Missing Fields
def test_ai_fill_eight_plus_missing_fields(client: TestClient, db_session: Session):
    tmpl, qset = setup_template_and_qset(db_session)
    q = Question(
        question_set_id=qset.id,
        row_number=3,
        data_json={
            "Question Prompt": "Which gas is released during photosynthesis?",
            "Option A": "Oxygen", "Option B": "Carbon Dioxide", "Option C": "Nitrogen", "Option D": "Hydrogen",
            "Correct Answer": "A",
            # 8 missing metadata fields:
            "Topic": "", "Subtopic": "", "Difficulty": "", "Marks": "",
            "Bloom Taxonomy": "", "Target Audience": "", "Explanation": "", "Tags": ""
        },
        source_metadata_json={"fields": {}},
        validation_json={"valid": True, "errors": []}
    )
    db_session.add(q)
    db_session.commit()
    db_session.refresh(q)

    mock_ai_response = {
        "Topic": {"value": "Biology", "status": "AI_INFERRED", "confidence": 0.99, "reason": "Plant biology"},
        "Subtopic": {"value": "Photosynthesis", "status": "AI_INFERRED", "confidence": 0.97, "reason": "Light reaction"},
        "Difficulty": {"value": "Easy", "status": "AI_INFERRED", "confidence": 0.92, "reason": "Fundamental fact"},
        "Marks": {"value": "1", "status": "AI_INFERRED", "confidence": 0.95, "reason": "Standard single mark"},
        "Bloom Taxonomy": {"value": "Remember", "status": "AI_INFERRED", "confidence": 0.90, "reason": "Recall concept"},
        "Target Audience": {"value": "Middle School", "status": "AI_INFERRED", "confidence": 0.88, "reason": "General science"},
        "Explanation": {"value": "Photosynthesis releases oxygen as byproduct.", "status": "AI_INFERRED", "confidence": 0.96, "reason": "Scientific explanation"},
        "Tags": {"value": "Botany, Science", "status": "AI_INFERRED", "confidence": 0.89, "reason": "Subject tags"},
    }

    with patch("app.services.azure_openai.fill_missing_fields_for_single_question", return_value=mock_ai_response):
        res = client.post(f"/api/questions/{q.id}/ai-fill", json={"context": {"subject": "Biology"}})
        assert res.status_code == 200
        data = res.json()
        assert data["ai_fill_result"]["resolved_count"] == 8
        assert data["ai_fill_result"]["unresolved_count"] == 0
        assert data["data_json"]["Topic"] == "Biology"
        assert data["data_json"]["Marks"] == "1"
        assert data["data_json"]["Explanation"] == "Photosynthesis releases oxygen as byproduct."

# 4. Test Question with No Missing Fields
def test_ai_fill_no_missing_fields(client: TestClient, db_session: Session):
    tmpl, qset = setup_template_and_qset(db_session)
    q = Question(
        question_set_id=qset.id,
        row_number=4,
        data_json={
            "Question Prompt": "Complete Question",
            "Option A": "A", "Option B": "B", "Option C": "C", "Option D": "D",
            "Correct Answer": "A",
            "Topic": "Complete", "Subtopic": "Complete", "Difficulty": "Hard", "Marks": "5",
            "Bloom Taxonomy": "Create", "Target Audience": "Advanced", "Explanation": "Detailed", "Tags": "Done"
        },
        source_metadata_json={"fields": {}},
        validation_json={"valid": True, "errors": []}
    )
    db_session.add(q)
    db_session.commit()
    db_session.refresh(q)

    res = client.post(f"/api/questions/{q.id}/ai-fill", json={"context": {}})
    assert res.status_code == 200
    data = res.json()
    assert data["ai_fill_result"]["status"] == "already_complete"
    assert data["ai_fill_result"]["resolved_count"] == 0

# 5. Test Question with Existing Source Values (Preserves Authoritative Values)
def test_ai_fill_preserves_existing_source_values(client: TestClient, db_session: Session):
    tmpl, qset = setup_template_and_qset(db_session)
    q = Question(
        question_set_id=qset.id,
        row_number=5,
        data_json={
            "Question Prompt": "What is H2O?",
            "Option A": "Water", "Option B": "Acid", "Option C": "Gas", "Option D": "Metal",
            "Correct Answer": "A",
            "Topic": "Authoritative Chemistry Source", # Must NOT be overwritten
            "Subtopic": "", # Missing
            "Difficulty": "Easy", # Must NOT be overwritten
            "Marks": "2", "Bloom Taxonomy": "Recall", "Target Audience": "Grade 7", "Explanation": "Water", "Tags": "Chem"
        },
        source_metadata_json={"fields": {}},
        validation_json={"valid": True, "errors": []}
    )
    db_session.add(q)
    db_session.commit()
    db_session.refresh(q)

    mock_ai_response = {
        "Subtopic": {"value": "Chemical Formulas", "status": "AI_INFERRED", "confidence": 0.95, "reason": "Water formula"}
    }

    with patch("app.services.azure_openai.fill_missing_fields_for_single_question", return_value=mock_ai_response) as mock_fn:
        res = client.post(f"/api/questions/{q.id}/ai-fill", json={"context": {"subject": "Chemistry"}})
        assert res.status_code == 200
        data = res.json()
        assert data["data_json"]["Topic"] == "Authoritative Chemistry Source"
        assert data["data_json"]["Difficulty"] == "Easy"
        assert data["data_json"]["Subtopic"] == "Chemical Formulas"
        # Ensure AI was only asked to fill the missing field ("Subtopic")
        requested_fields = mock_fn.call_args[1]["missing_fields"]
        assert requested_fields == ["Subtopic"]

# 6. Test Question Where AI Cannot Confidently Infer a Field (Review Required)
def test_ai_fill_low_confidence_requires_review(client: TestClient, db_session: Session):
    tmpl, qset = setup_template_and_qset(db_session)
    q = Question(
        question_set_id=qset.id,
        row_number=6,
        data_json={
            "Question Prompt": "Ambiguous fragment question ...",
            "Option A": "1", "Option B": "2", "Option C": "3", "Option D": "4",
            "Correct Answer": "C",
            "Topic": "Math", "Subtopic": "", "Difficulty": "", "Marks": "1",
            "Bloom Taxonomy": "Recall", "Target Audience": "General", "Explanation": "N/A", "Tags": "Test"
        },
        source_metadata_json={"fields": {}},
        validation_json={"valid": True, "errors": []}
    )
    db_session.add(q)
    db_session.commit()
    db_session.refresh(q)

    mock_ai_response = {
        "Subtopic": {"value": "Unknown", "status": "UNRESOLVED", "confidence": 0.30, "reason": "Question is too ambiguous to identify subtopic"},
        "Difficulty": {"value": "Medium", "status": "AI_INFERRED", "confidence": 0.55, "reason": "Low confidence guess without full context"}
    }

    with patch("app.services.azure_openai.fill_missing_fields_for_single_question", return_value=mock_ai_response):
        res = client.post(f"/api/questions/{q.id}/ai-fill", json={"context": {}})
        assert res.status_code == 200
        data = res.json()
        assert data["ai_fill_result"]["resolved_count"] == 0
        assert data["ai_fill_result"]["review_required_count"] == 1
        assert data["ai_fill_result"]["unresolved_count"] == 1
        # Inferred value with confidence < 0.70 is NOT saved into data_json
        assert data["data_json"]["Difficulty"] == ""
        # Stored in source_metadata.fields as REVIEW_REQUIRED
        assert data["source_metadata"]["fields"]["Difficulty"]["status"] == "REVIEW_REQUIRED"
        assert data["source_metadata"]["fields"]["Difficulty"]["confidence"] == 0.55

# 7 & 8. Test Multiple Questions with Different Missing Fields & Bulk Fill Endpoint
def test_batch_ai_fill_across_assessment(client: TestClient, db_session: Session):
    tmpl, qset = setup_template_and_qset(db_session)
    q1 = Question(
        question_set_id=qset.id,
        row_number=1,
        data_json={
            "Question Prompt": "Q1 text",
            "Option A": "A", "Option B": "B", "Option C": "C", "Option D": "D",
            "Correct Answer": "A",
            "Topic": "", "Subtopic": "Sub 1", "Difficulty": "Easy", "Marks": "1",
            "Bloom Taxonomy": "Recall", "Target Audience": "G1", "Explanation": "Exp1", "Tags": "T1"
        },
        source_metadata_json={"fields": {}},
        validation_json={"valid": True, "errors": []}
    )
    q2 = Question(
        question_set_id=qset.id,
        row_number=2,
        data_json={
            "Question Prompt": "Q2 text",
            "Option A": "A", "Option B": "B", "Option C": "C", "Option D": "D",
            "Correct Answer": "B",
            "Topic": "Topic 2", "Subtopic": "", "Difficulty": "", "Marks": "2",
            "Bloom Taxonomy": "Apply", "Target Audience": "G2", "Explanation": "Exp2", "Tags": "T2"
        },
        source_metadata_json={"fields": {}},
        validation_json={"valid": True, "errors": []}
    )
    q3 = Question(
        question_set_id=qset.id,
        row_number=3,
        data_json={
            "Question Prompt": "Q3 text",
            "Option A": "A", "Option B": "B", "Option C": "C", "Option D": "D",
            "Correct Answer": "C",
            "Topic": "Topic 3", "Subtopic": "Sub 3", "Difficulty": "Hard", "Marks": "3",
            "Bloom Taxonomy": "Analyze", "Target Audience": "G3", "Explanation": "Exp3", "Tags": "T3"
        },
        source_metadata_json={"fields": {}},
        validation_json={"valid": True, "errors": []}
    )
    db_session.add_all([q1, q2, q3])
    db_session.commit()
    db_session.refresh(q1)
    db_session.refresh(q2)
    db_session.refresh(q3)

    def mock_single_fill(question_data, missing_fields, template_schema, context):
        res = {}
        for f in missing_fields:
            res[f] = {
                "value": f"Inferred {f}",
                "status": "AI_INFERRED",
                "confidence": 0.95,
                "reason": "Batch inference test"
            }
        return res

    with patch("app.services.azure_openai.fill_missing_fields_for_single_question", side_effect=mock_single_fill):
        response = client.post(
            "/api/questions/batch-ai-fill",
            json={
                "question_ids": [q1.id, q2.id, q3.id],
                "context": {"subject": "Test Assessment"}
            }
        )
        assert response.status_code == 200
        payload = response.json()
        summary = payload["summary"]
        assert summary["questions_processed"] == 3
        assert summary["fields_filled"] == 3  # Q1 had 1 missing, Q2 had 2 missing, Q3 had 0 missing
        assert summary["failed"] == 0
        assert len(payload["questions"]) == 3
        
        q1_res = next(q for q in payload["questions"] if q["id"] == q1.id)
        assert q1_res["data_json"]["Topic"] == "Inferred Topic"
        
        q2_res = next(q for q in payload["questions"] if q["id"] == q2.id)
        assert q2_res["data_json"]["Subtopic"] == "Inferred Subtopic"
        assert q2_res["data_json"]["Difficulty"] == "Inferred Difficulty"
