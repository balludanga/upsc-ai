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


# --- Chat ---

class ChatTurnRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    session_id: Optional[int] = None


class ChatSuggestion(BaseModel):
    session_id: int
    question: str
    answer: str
    suggestions: List[str]
    title: str


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    suggestions: List[str] = []
    created_at: str


class ChatSessionOut(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ChatSessionDetail(ChatSessionOut):
    messages: List[ChatMessageOut] = []


# --- Quiz ---

class QuizGenerateRequest(BaseModel):
    topic: Optional[str] = Field(default=None, max_length=120)
    subject: Optional[str] = Field(default=None, max_length=80)
    num_questions: int = Field(default=5, ge=1, le=20)


class QuizQuestion(BaseModel):
    id: int
    bank_id: int
    question: str
    options: List[str]
    year: int
    subject: str
    topic: str
    source: str
    source_url: Optional[str] = None
    difficulty: int = 2


class QuizGenerateResponse(BaseModel):
    questions: List[QuizQuestion]


class QuizPracticeQuestion(QuizQuestion):
    pass


class QuizTopicOut(BaseModel):
    name: str
    question_count: int


class QuizSubjectOut(BaseModel):
    name: str
    question_count: int
    topics: List[QuizTopicOut]


class QuizCatalogResponse(BaseModel):
    subjects: List[QuizSubjectOut]


class QuizSubmitRequest(BaseModel):
    quiz_attempt_id: int
    selected_option: Literal["A", "B", "C", "D"]


class QuizSubmitResponse(BaseModel):
    correct: bool
    correct_option: Literal["A", "B", "C", "D"]
    selected_option: Literal["A", "B", "C", "D"]


class QuizReviewRequest(BaseModel):
    attempt_ids: List[int] = Field(min_length=1, max_length=20)


class QuizReviewItem(BaseModel):
    attempt_id: int
    correct_option: Literal["A", "B", "C", "D"]


class QuizReviewResponse(BaseModel):
    answers: List[QuizReviewItem]


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


class MainsTranscriptionOut(BaseModel):
    answer: str
    transcription: dict


class MainsEvaluateUploadResponse(MainsTranscriptionOut):
    question: str
    paper: str
    word_limit: int
    evaluation: dict
