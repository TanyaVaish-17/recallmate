from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.ownership import get_owned_exam, get_owned_subject
from app.db.session import get_db
from app.models.exam import Exam
from app.models.user import User
from app.schemas.exam import ExamCreate, ExamRead, ExamUpdate

router = APIRouter(prefix="/exams", tags=["exams"])


@router.get("", response_model=list[ExamRead])
def list_exams(
    subject_id: int | None = None,
    upcoming_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Exam).where(Exam.user_id == current_user.id)
    if subject_id is not None:
        stmt = stmt.where(Exam.subject_id == subject_id)
    if upcoming_only:
        stmt = stmt.where(Exam.exam_date >= date.today())
    stmt = stmt.order_by(Exam.exam_date, Exam.id).offset(skip).limit(limit)
    return list(db.scalars(stmt))


@router.post("", response_model=ExamRead, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_subject(db, payload.subject_id, current_user)

    exam = Exam(
        user_id=current_user.id,
        subject_id=payload.subject_id,
        title=payload.title,
        exam_date=payload.exam_date,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@router.patch("/{exam_id}", response_model=ExamRead)
def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exam = get_owned_exam(db, exam_id, current_user)

    if payload.title is not None:
        exam.title = payload.title
    if payload.exam_date is not None:
        exam.exam_date = payload.exam_date

    db.commit()
    db.refresh(exam)
    return exam


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exam = get_owned_exam(db, exam_id, current_user)
    db.delete(exam)
    db.commit()