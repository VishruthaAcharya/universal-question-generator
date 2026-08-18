# Universal Question Generator

Simple V1 application for converting question sources such as PYQ PDFs into CET-style MCQs and exporting them into a target CSV/XLSX template.

## Architecture

Next.js frontend → FastAPI backend → PyMuPDF/pandas → OpenAI → Pydantic validation → CSV/XLSX export.

V1 intentionally does **not** use PostgreSQL, Redis, Celery, S3, authentication, or a job database.

## Run locally

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

Backend docs: http://localhost:8000/docs

## AI configuration

Put the OpenAI key in `backend/.env`.

```env
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4.1-mini
```

If no API key is provided, the backend uses deterministic mock generation so the full UI/export flow can still be tested.

## Supported V1 source files

PDF, TXT, CSV, XLSX.

## Supported target template

The primary V1 template uses:

- Question
- Question Topic
- Sub Topic
- Answer 1
- Answer 2
- Answer 3
- Answer 4
- Difficulty Level
- Correct Answer
- Score

## Tests

```powershell
cd backend
pytest
```


## PostgreSQL persistence

The V1 application now persists data in PostgreSQL using SQLAlchemy and Alembic.

### Tables
- `question_sets`: one generated/imported batch
- `questions`: individual question records
- `templates`: target template column definitions

### Local database
Create `question_generator` in PostgreSQL and set `backend/.env`:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/question_generator
```

Then:

```powershell
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Docker
Run:

```powershell
docker compose up --build
```

PostgreSQL is started automatically and migrations run before FastAPI starts.
