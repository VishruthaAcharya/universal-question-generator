import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Template(Base):
    __tablename__ = "templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schema_json: Mapped[dict] = mapped_column(JSON)  # stores list of column names, metadata, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    question_sets: Mapped[list["QuestionSet"]] = relationship(back_populates="template")

class QuestionSet(Base):
    __tablename__ = "question_sets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id: Mapped[str | None] = mapped_column(ForeignKey("templates.id", ondelete="SET NULL"), nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    questions: Mapped[list["Question"]] = relationship(back_populates="question_set", cascade="all, delete-orphan")
    template: Mapped[Template | None] = relationship(back_populates="question_sets")

class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_set_id: Mapped[str] = mapped_column(ForeignKey("question_sets.id", ondelete="CASCADE"))
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_json: Mapped[dict] = mapped_column(JSON)  # dynamic columns mapped from source
    validation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="GENERATED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    question_set: Mapped["QuestionSet"] = relationship(back_populates="questions")

