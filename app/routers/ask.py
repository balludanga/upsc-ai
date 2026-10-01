from datetime import date, datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.chat import answer_chat_turn, starter_topics
from app.config import settings
from app.database import get_db
from app.models import (
    ChatMessage,
    ChatSession,
    DailyUsage,
    User,
)
from app.rag import answer_question
from app.schemas import (
    AskRequest,
    AskResponse,
    ChatMessageOut,
    ChatSessionDetail,
    ChatSessionOut,
    ChatSuggestion,
    ChatTurnRequest,
)

router = APIRouter(prefix="/ask", tags=["ask"])


def _check_and_increment_usage(db: Session, user: User):
    if settings.free_tier_daily_limit <= 0:
        return

    today = date.today()

    usage = (
        db.query(DailyUsage)
        .filter(
            DailyUsage.user_id == user.id,
            DailyUsage.usage_date == today,
        )
        .first()
    )

    if usage is None:
        usage = DailyUsage(
            user_id=user.id,
            usage_date=today,
            ask_count=0,
        )
        db.add(usage)
        db.flush()

    if usage.ask_count >= settings.free_tier_daily_limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily free limit of "
                f"{settings.free_tier_daily_limit} questions reached. "
                "Try again tomorrow."
            ),
        )

    usage.ask_count += 1
    db.commit()


@router.post("", response_model=AskResponse)
def ask(
    request: AskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _check_and_increment_usage(db, user)

    answer, _sources = answer_question(request.question)

    return AskResponse(answer=answer)


# -----------------------------------------------------------------------------
# Study chat
# -----------------------------------------------------------------------------

def _isoformat(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return ""


def _session_out(session: ChatSession) -> ChatSessionOut:
    return ChatSessionOut(
        id=session.id,
        title=session.title,
        created_at=_isoformat(session.created_at),
        updated_at=_isoformat(session.updated_at),
        message_count=len(session.messages),
    )


def _message_out(message: ChatMessage) -> ChatMessageOut:
    suggestions = message.suggestions

    return ChatMessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        suggestions=(
            [str(item) for item in suggestions]
            if isinstance(suggestions, list)
            else []
        ),
        created_at=_isoformat(message.created_at),
    )


def _build_title(question: str) -> str:
    """
    Derive a short session title from the opening question.
    """
    cleaned = " ".join(question.split()).strip()

    if not cleaned:
        return "New chat"

    if len(cleaned) <= 60:
        return cleaned

    return cleaned[:57].rstrip() + "..."


def _get_session(
    db: Session,
    session_id: int,
    user: User,
) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
        .first()
    )

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="That chat session was not found.",
        )

    return session


def _should_retitle(session: ChatSession) -> bool:
    """
    Only the opening question should name the chat.
    """
    return (
        not session.messages
        or session.title in ("", "New chat")
    )


@router.get("/chat/starter-topics")
def get_starter_topics(
    user: User = Depends(get_current_user),
):
    return {"topics": starter_topics()}


@router.post("/chat", response_model=ChatSuggestion)
def chat_turn(
    request: ChatTurnRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _check_and_increment_usage(db, user)

    question = request.question.strip()

    if request.session_id is not None:
        session = _get_session(db, request.session_id, user)
    else:
        session = ChatSession(
            user_id=user.id,
            title="New chat",
        )
        db.add(session)
        db.flush()

    history = [
        {"role": message.role, "content": message.content}
        for message in session.messages
    ]

    db.add(
        ChatMessage(
            session_id=session.id,
            role="user",
            content=question,
        )
    )

    result = answer_chat_turn(
        question=question,
        history=history,
    )

    if _should_retitle(session):
        session.title = _build_title(question)

    reply = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=result["answer"],
        suggestions=result["suggestions"],
    )

    db.add(reply)
    db.commit()

    return ChatSuggestion(
        session_id=session.id,
        question=question,
        answer=result["answer"],
        suggestions=result["suggestions"],
        title=session.title,
    )


@router.get("/chat/sessions", response_model=List[ChatSessionOut])
def list_chat_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(50)
        .all()
    )

    return [_session_out(session) for session in sessions]


@router.get(
    "/chat/sessions/{session_id}",
    response_model=ChatSessionDetail,
)
def get_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = _get_session(db, session_id, user)

    return ChatSessionDetail(
        **_session_out(session).model_dump(),
        messages=[
            _message_out(message)
            for message in session.messages
        ],
    )


@router.delete("/chat/sessions/{session_id}")
def delete_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = _get_session(db, session_id, user)

    db.delete(session)
    db.commit()

    return {"deleted": True, "id": session_id}
