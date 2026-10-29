from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.ownership import get_owned_topic
from app.db.session import get_db
from app.models.topic import Topic
from app.models.user import User
from app.schemas.topic import TopicRead, TopicUpdate

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("/{topic_id}", response_model=TopicRead)
def get_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_owned_topic(db, topic_id, current_user)


@router.patch("/{topic_id}", response_model=TopicRead)
def update_topic(
    topic_id: int,
    payload: TopicUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    topic = get_owned_topic(db, topic_id, current_user)

    if payload.name is not None and payload.name != topic.name:
        duplicate = db.scalar(
            select(Topic).where(Topic.subject_id == topic.subject_id, Topic.name == payload.name)
        )
        if duplicate:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Topic already exists")
        topic.name = payload.name
    if payload.difficulty is not None:
        topic.difficulty = payload.difficulty
    if payload.estimated_minutes is not None:
        topic.estimated_minutes = payload.estimated_minutes

    db.commit()
    db.refresh(topic)
    return topic


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    topic = get_owned_topic(db, topic_id, current_user)
    db.delete(topic)
    db.commit()