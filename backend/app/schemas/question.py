from typing import Literal
from pydantic import BaseModel, Field, field_validator

class Question(BaseModel):
    question: str = Field(min_length=1)
    topic: str = Field(default="")
    subtopic: str = Field(default="")
    answer_1: str = Field(min_length=1)
    answer_2: str = Field(min_length=1)
    answer_3: str = Field(min_length=1)
    answer_4: str = Field(min_length=1)
    difficulty: Literal["Easy", "Medium", "Hard"]
    correct_answer: str = Field(min_length=1)
    score: int = Field(default=1, ge=0)

    @field_validator("correct_answer")
    @classmethod
    def correct_answer_must_match_option(cls, value, info):
        data = info.data
        options = [data.get(f"answer_{i}") for i in range(1, 5)]
        if options and value not in options:
            raise ValueError("correct_answer must exactly match one of the four options")
        return value

    @field_validator("answer_4")
    @classmethod
    def options_must_be_unique(cls, value, info):
        options = [info.data.get(f"answer_{i}") for i in range(1, 4)] + [value]
        if len(set(options)) != 4:
            raise ValueError("All four options must be unique")
        return value

class QuestionList(BaseModel):
    questions: list[Question]

class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = []
