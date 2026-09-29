from typing import List, Optional, Literal
from pydantic import BaseModel, EmailStr, Field


# --- Auth ---

class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Ask ---

class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class AskResponse(BaseModel):
    answer: str


# --- Quiz ---

class QuizGenerateRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    num_questions: int = Field(default=5, ge=1, le=20)


class QuizQuestion(BaseModel):
    id: int
    question: str
    options: List[str]


class QuizGenerateResponse(BaseModel):
    questions: List[QuizQuestion]


class QuizSubmitRequest(BaseModel):
    quiz_attempt_id: int
    selected_option: Literal["A", "B", "C", "D"]


class QuizSubmitResponse(BaseModel):
    correct: bool
    correct_option: Literal["A", "B", "C", "D"]


# --- Personal study tracking ---

class StudySessionCreate(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    mode: str = Field(default="study", min_length=2, max_length=40)
    minutes: int = Field(ge=1, le=720)
    notes: Optional[str] = Field(default=None, max_length=5000)


class StudySessionOut(StudySessionCreate):
    id: int
    created_at: str


class StudyPlanItem(BaseModel):
    topic: str
    mode: str
    minutes: int
    reason: str


class StudyPlanResponse(BaseModel):
    date: str
    total_minutes: int
    items: List[StudyPlanItem]


class StudyDashboard(BaseModel):
    today_minutes: int
    total_minutes: int
    current_streak_days: int
    quizzes_attempted: int
    quiz_accuracy_percent: float
    weak_topics: List[str]


# --- Mains ---

class MainsDraftRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    paper: str = Field(default="GS2", min_length=2, max_length=20)
    word_limit: int = Field(default=250, ge=100, le=1000)


class MainsDraftResponse(BaseModel):
    answer: str
    paper: str
    word_limit: int
    structure: dict


class MainsEvaluateRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    answer: str = Field(min_length=10, max_length=12000)
    paper: str = Field(default="GS2", min_length=2, max_length=20)
    word_limit: int = Field(default=250, ge=100, le=1000)


class MainsEvaluateResponse(BaseModel):
    question: str
    paper: str
    word_limit: int
    answer: str
    evaluation: dict
