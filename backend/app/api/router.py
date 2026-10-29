from fastapi import APIRouter

from app.api.routes import auth, exams, plan, questions, quizzes, subjects, topics

from app.api.routes import model_info
api_router.include_router(model_info.router)

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(subjects.router)
api_router.include_router(topics.router)
api_router.include_router(exams.router)
api_router.include_router(questions.router)
api_router.include_router(quizzes.router)
api_router.include_router(plan.router)