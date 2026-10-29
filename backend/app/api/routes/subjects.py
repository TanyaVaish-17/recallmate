from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.api.ownership import get_owned_subject
from app.db.session import get_db
from app.models.subject import Subject
from app.models.topic import Topic
from app.models.user import User
from app.schemas.subject import SubjectCreate, SubjectDetail, SubjectRead, SubjectUpdate
from app.schemas.topic import TopicCreate, TopicRead

router = APIRouter(prefix="/subjects", tags=["subjects"])


# Subjects
@router.get("", response_model=list[SubjectRead])
def list_subjects(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(Subject)
        .where(Subject.user_id == current_user.id)
        .order_by(Subject.id)
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt))


@router.post("", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
def create_subject(
    payload: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    duplicate = db.scalar(
        select(Subject).where(Subject.user_id == current_user.id, Subject.name == payload.name)
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Subject already exists")

    subject = Subject(user_id=current_user.id, name=payload.name, color=payload.color)
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@router.get("/{subject_id}", response_model=SubjectDetail)
def get_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subject = db.scalar(
        select(Subject)
        .options(selectinload(Subject.topics))
        .where(Subject.id == subject_id, Subject.user_id == current_user.id)
    )
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    return subject


@router.patch("/{subject_id}", response_model=SubjectRead)
def update_subject(
    subject_id: int,
    payload: SubjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subject = get_owned_subject(db, subject_id, current_user)

    if payload.name is not None and payload.name != subject.name:
        duplicate = db.scalar(
            select(Subject).where(Subject.user_id == current_user.id, Subject.name == payload.name)
        )
        if duplicate:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Subject already exists")
        subject.name = payload.name
    if payload.color is not None:
        subject.color = payload.color

    db.commit()
    db.refresh(subject)
    return subject


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subject = get_owned_subject(db, subject_id, current_user)
    db.delete(subject)
    db.commit()


# Topics under a subject
@router.get("/{subject_id}/topics", response_model=list[TopicRead])
def list_topics(
    subject_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_subject(db, subject_id, current_user)
    stmt = (
        select(Topic)
        .where(Topic.subject_id == subject_id)
        .order_by(Topic.id)
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt))


@router.post("/{subject_id}/topics", response_model=TopicRead, status_code=status.HTTP_201_CREATED)
def create_topic(
    subject_id: int,
    payload: TopicCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_subject(db, subject_id, current_user)

    duplicate = db.scalar(
        select(Topic).where(Topic.subject_id == subject_id, Topic.name == payload.name)
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Topic already exists")

    topic = Topic(
        subject_id=subject_id,
        name=payload.name,
        difficulty=payload.difficulty,
        estimated_minutes=payload.estimated_minutes,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic