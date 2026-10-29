from fastapi import APIRouter

from app.api.routes import auth, subjects, topics

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(subjects.router)
api_router.include_router(topics.router)