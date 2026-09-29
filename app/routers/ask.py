from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import DailyUsage, User
from app.rag import answer_question
from app.schemas import AskRequest, AskResponse

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
