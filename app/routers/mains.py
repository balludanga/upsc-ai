from typing import List, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.evaluator import evaluate_mains_answer
from app.models import MainsEvaluation, User
from app.ocr import UploadError, transcribe_uploads
from app.rag import draft_mains_answer, normalize_paper
from app.schemas import (
    MainsDraftRequest,
    MainsDraftResponse,
    MainsEvaluateRequest,
    MainsEvaluateResponse,
    MainsEvaluateUploadResponse,
    MainsTranscriptionOut,
)

router = APIRouter(prefix="/mains", tags=["mains"])


def _read_uploads(
    files: List[UploadFile],
) -> List[Tuple[str, str, bytes]]:
    """
    Read multipart uploads into memory, enforcing the total size budget.
    """
    uploads: List[Tuple[str, str, bytes]] = []
    total = 0

    for upload in files:
        if upload is None or not upload.filename:
            continue

        data = upload.file.read()

        if not data:
            continue

        total += len(data)

        if total > settings.upload_max_bytes:
            raise UploadError(
                "The upload is too large. Keep it under "
                f"{settings.upload_max_bytes // (1024 * 1024)} MB "
                "by uploading fewer pages at a time."
            )

        uploads.append(
            (
                upload.filename,
                upload.content_type or "",
                data,
            )
        )

    if not uploads:
        raise UploadError(
            "Attach at least one photo or PDF of your handwritten answer."
        )

    return uploads


@router.post("/draft", response_model=MainsDraftResponse)
def draft_answer(
    request: MainsDraftRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        answer, _sources, structure = draft_mains_answer(
            question=request.question,
            paper=request.paper,
            word_limit=request.word_limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return MainsDraftResponse(
        answer=answer,
        paper=normalize_paper(request.paper),
        word_limit=request.word_limit,
        structure=structure,
    )


@router.post(
    "/evaluate",
    response_model=MainsEvaluateResponse,
)
def evaluate_answer(
    request: MainsEvaluateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        evaluation = evaluate_mains_answer(
            question=request.question,
            answer=request.answer,
            paper=normalize_paper(request.paper),
            word_limit=request.word_limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    record = MainsEvaluation(
        user_id=user.id,
        question=request.question,
        paper=normalize_paper(request.paper),
        word_limit=request.word_limit,
        answer=request.answer,
        evaluation=evaluation,
    )

    db.add(record)
    db.commit()

    return MainsEvaluateResponse(
        question=request.question,
        paper=normalize_paper(request.paper),
        word_limit=request.word_limit,
        answer=request.answer,
        evaluation=evaluation,
    )


@router.post(
    "/transcribe",
    response_model=MainsTranscriptionOut,
)
def transcribe_answer_files(
    files: List[UploadFile] = File(...),
    user: User = Depends(get_current_user),
):
    """
    Read handwritten answer photos / scanned PDFs into plain text so the
    candidate can proofread before evaluating.
    """
    try:
        transcription = transcribe_uploads(_read_uploads(files))
    except UploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return MainsTranscriptionOut(
        answer=transcription.text,
        transcription=transcription.to_dict(),
    )


@router.post(
    "/evaluate-upload",
    response_model=MainsEvaluateUploadResponse,
)
def evaluate_answer_files(
    question: str = Form(..., min_length=3, max_length=2000),
    paper: str = Form(default="GS2"),
    word_limit: int = Form(default=250, ge=100, le=1000),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Transcribe uploaded handwritten answers, then evaluate them exactly
    like a typed answer.
    """
    try:
        transcription = transcribe_uploads(_read_uploads(files))
    except UploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        evaluation = evaluate_mains_answer(
            question=question,
            answer=transcription.text,
            paper=normalize_paper(paper),
            word_limit=word_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record = MainsEvaluation(
        user_id=user.id,
        question=question,
        paper=normalize_paper(paper),
        word_limit=word_limit,
        answer=transcription.text,
        evaluation=evaluation,
    )

    db.add(record)
    db.commit()

    return MainsEvaluateUploadResponse(
        question=question,
        paper=normalize_paper(paper),
        word_limit=word_limit,
        answer=transcription.text,
        evaluation=evaluation,
        transcription=transcription.to_dict(),
    )


@router.get("/papers")
def list_papers():
    return {
        "papers": [
            {
                "id": "GS1",
                "name": "GS1 - Indian Heritage & Culture, History, Geography",
                "description": "Indian Heritage & Culture, History, Geography of the World & Society",
            },
            {
                "id": "GS2",
                "name": "GS2 - Governance, Constitution, Polity, Social Justice, IR",
                "description": "Governance, Constitution, Polity, Social Justice, International Relations",
            },
            {
                "id": "GS3",
                "name": "GS3 - Economy, Agriculture, Environment, S&T, Security",
                "description": "Technology, Economic Development, Bio-diversity, Environment, Security, Disaster Management",
            },
            {
                "id": "GS4",
                "name": "GS4 - Ethics, Integrity, Aptitude",
                "description": "Ethics, Integrity, Aptitude",
            },
            {
                "id": "ESSAY",
                "name": "Essay Paper",
                "description": "Essay writing on philosophical, social, economic, political topics",
            },
            {
                "id": "OPTIONAL",
                "name": "Optional Subject",
                "description": "Optional subject specific answers",
            },
        ]
    }
