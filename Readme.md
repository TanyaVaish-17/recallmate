# RecallMate

AI-powered adaptive revision scheduler for college students. A Transformer-based knowledge-tracing model predicts topic-level performance, and a transparent scheduler turns those predictions into daily revision plans.

## Structure

- `backend/` FastAPI, SQLAlchemy, Alembic
- `frontend/` React, Vite, TypeScript, Tailwind
- `ml/` dataset pipeline, Transformer model, training, evaluation
- `docs/` architecture, API notes, experiment report

Setup instructions are added as each module is built.

## Backend setup

```bash
cd backend
python -m venv .venv
# activate: .venv\Scripts\Activate.ps1 (Windows) or source .venv/bin/activate (Mac/Linux)
pip install -r requirements.txt
cp ../.env.example ../.env   # then fill in DATABASE_URL and JWT_SECRET
alembic upgrade head
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs