import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class QuestionSet(Base):
    __tablename__ = "question_sets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255), default="")
    source_file: Mapped[str] = mapped_column(String(500), default="")
    generation_mode: Mapped[str] = mapped_column(String(50), default="CET_MCQ")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    questions: Mapped[list["Question"]] = relationship(back_populates="question_set", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_set_id: Mapped[str] = mapped_column(ForeignKey("question_sets.id", ondelete="CASCADE"))
    question: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(255), default="")
    subtopic: Mapped[str] = mapped_column(String(255), default="")
    answer_1: Mapped[str] = mapped_column(Text)
    answer_2: Mapped[str] = mapped_column(Text)
    answer_3: Mapped[str] = mapped_column(Text)
    answer_4: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(20))
    correct_answer: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer, default=1)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="GENERATED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    question_set: Mapped["QuestionSet"] = relationship(back_populates="questions")

class Template(Base):
    __tablename__ = "templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    columns: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
