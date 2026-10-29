from fastapi import APIRouter

from app.api.routes import auth, exams, questions, quizzes, subjects, topics

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(subjects.router)
api_router.include_router(topics.router)
api_router.include_router(exams.router)
api_router.include_router(questions.router)
api_router.include_router(quizzes.router)