<div align="center">

# 🧠 RecallMate

### AI-powered adaptive revision scheduler for college students

A Transformer-based **knowledge-tracing model** estimates how likely you are to answer each topic correctly,
and a transparent scheduler turns those estimates into a daily revision plan.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind-4-06B6D4?logo=tailwindcss&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?logo=pytorch&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)

![Dashboard](docs/screenshots/dashboard.png)

</div>

---

## 📑 Table of Contents

- [✨ Features](#-features)
- [🖼️ Screenshots](#️-screenshots)
- [🏗️ How It Works](#️-how-it-works)
- [🧰 Tech Stack](#-tech-stack)
- [📁 Project Structure](#-project-structure)
- [🚀 Getting Started](#-getting-started)
- [🤖 Training the Model](#-training-the-model)
- [🔌 API Overview](#-api-overview)
- [🧪 Running Tests](#-running-tests)
- [📊 Model Results](#-model-results)
- [🛠️ Troubleshooting](#️-troubleshooting)
- [🗺️ Roadmap](#️-roadmap)

---

## ✨ Features

| | Feature | Description |
|---|---|---|
| 🔐 | **Authentication** | Register / login with JWT tokens and Argon2 password hashing |
| 📚 | **Subjects & Topics** | Organise what you study, with colours, difficulty and estimated time per topic |
| 📝 | **Exams** | Add exam dates; the planner prioritises subjects with exams coming up |
| ❓ | **Question Bank** | Multiple-choice questions with explanations, per topic |
| ✅ | **Quizzes** | Take topic quizzes; every answer is stored as a learning event |
| 🤖 | **Transformer Predictions** | A causal Transformer estimates P(correct) for each topic from your answer history |
| 📅 | **Adaptive Revision Plan** | Daily sessions ranked by model estimate, exam proximity, recency and missed sessions |
| 🔁 | **Auto Re-planning** | Submitting a quiz or completing/skipping a session regenerates the plan |
| 📈 | **Analytics** | Score trends, subject accuracy, weak topics and session completion |
| 🔍 | **Honest Model Page** | Shows the real measured results, baselines and limitations. Nothing is fabricated |

> **Note:** if no trained checkpoint exists, RecallMate does **not** invent predictions. It says the model is
> not trained and plans without model estimates.

---

## 🖼️ Screenshots

<table>
  <tr>
    <td align="center"><b>🏠 Dashboard</b><br><img src="docs/screenshots/dashboard.png" width="420"></td>
    <td align="center"><b>📚 Subjects</b><br><img src="docs/screenshots/subjects.png" width="420"></td>
  </tr>
  <tr>
    <td align="center"><b>📝 Quiz</b><br><img src="docs/screenshots/quiz.png" width="420"></td>
    <td align="center"><b>📅 Revision Plan</b><br><img src="docs/screenshots/plan.png" width="420"></td>
  </tr>
  <tr>
    <td align="center"><b>📈 Analytics</b><br><img src="docs/screenshots/analytics.png" width="420"></td>
    <td align="center"><b>🧠 Model</b><br><img src="docs/screenshots/model.png" width="420"></td>
  </tr>
  <tr>
    <td align="center"><b>🔐 Login</b><br><img src="docs/screenshots/login.png" width="420"></td>
    <td align="center"><b>🔌 API Docs (Swagger)</b><br><img src="docs/screenshots/api-docs.png" width="420"></td>
  </tr>
</table>

---

## 🏗️ How It Works

```mermaid
flowchart LR
    A[📝 Student takes quiz] --> B[(🗄️ Learning events<br/>PostgreSQL)]
    B --> C[🤖 Transformer<br/>knowledge tracing]
    C -->|P correct per topic| D[📅 Scheduler]
    E[🎓 Exam dates] --> D
    F[⏱️ Days since revision<br/>missed sessions] --> D
    D --> G[✅ Daily revision plan]
    G -->|complete / skip| B
```

1. **Record**: every quiz answer is saved as a learning event (topic, correctness, time).
2. **Predict**: the student's history is fed to a compact causal Transformer, which outputs the probability of answering each topic correctly *now*.
3. **Schedule**: the planner combines that estimate with exam dates, time since last revision and missed sessions, then fits sessions into the student's daily study budget.
4. **Learn**: when the next quiz on a topic is submitted, the actual accuracy is stored next to the earlier prediction so predicted vs. actual can be compared.

### 🤖 The model

- Compact **causal Transformer encoder** (pre-LayerNorm, 2 blocks, 4 heads, about 99K parameters)
- Input per step: question embedding + topic embedding + previous-answer embedding + 5 numeric features + positional embedding
- Numeric features: time gap since last answer, time gap since last answer on the same topic, prior attempts at the question and topic, and a "revised since last time" flag
- **No future leakage**: the answer at step *t* is never an input at step *t*, and attention is causal
- RecallMate's own questions are not in the training vocabulary, so ids are mapped to `UNK` and the model relies on history, timing and revision flags

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| 🎨 **Frontend** | React 19, Vite, Tailwind CSS 4, React Router, Recharts, Lucide icons |
| ⚙️ **Backend** | FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| 🗄️ **Database** | PostgreSQL (SQLite in-memory for tests) |
| 🔐 **Auth** | JWT (PyJWT), Argon2 (pwdlib) |
| 🤖 **ML** | PyTorch, NumPy, pandas, scikit-learn |
| 🧪 **Testing** | pytest, httpx |

---

## 📁 Project Structure

```
recallmate/
├── 📄 README.md
├── 📄 .env.example              # copy to .env and fill in
│
├── ⚙️ backend/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── alembic.ini
│   ├── alembic/                 # database migrations
│   │   └── versions/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── api/
│   │   │   ├── router.py        # registers all routers under /api
│   │   │   ├── deps.py          # current-user dependency
│   │   │   ├── ownership.py     # per-user access checks
│   │   │   └── routes/
│   │   │       ├── auth.py
│   │   │       ├── subjects.py
│   │   │       ├── topics.py
│   │   │       ├── exams.py
│   │   │       ├── questions.py
│   │   │       ├── quizzes.py
│   │   │       ├── plan.py      # plan, sessions, model status, analytics
│   │   │       └── model_info.py# endpoints used by the React frontend
│   │   ├── core/                # config + security
│   │   ├── db/                  # engine, session, Base
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   └── services/
│   │       ├── prediction.py    # loads the Transformer, makes predictions
│   │       ├── scheduler.py     # pure planning logic
│   │       └── planner.py       # DB glue: states -> plan -> sessions
│   ├── scripts/
│   │   └── seed_demo.py         # demo student with subjects/topics/questions
│   └── tests/
│
├── 🎨 frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   └── src/
│       ├── main.jsx
│       ├── App.jsx              # routes
│       ├── Layout.jsx           # sidebar / navigation
│       ├── api.js               # all backend calls
│       ├── auth.jsx             # auth context
│       ├── SessionCard.jsx
│       ├── ui.jsx               # shared components + hooks
│       └── pages/
│           ├── Login.jsx
│           ├── Dashboard.jsx
│           ├── Subjects.jsx
│           ├── Quiz.jsx
│           ├── Plan.jsx
│           ├── Analytics.jsx
│           └── Model.jsx
│
├── 🤖 ml/
│   ├── config.py
│   ├── requirements.txt
│   ├── data/
│   │   ├── synthetic.py         # simulated students
│   │   ├── assistments.py       # ASSISTments loader
│   │   ├── preprocess.py        # features (no leakage)
│   │   └── build_dataset.py
│   ├── model/
│   │   ├── transformer.py       # causal Transformer encoder
│   │   ├── loss.py
│   │   ├── dataset.py
│   │   └── io.py                # save / load checkpoint
│   ├── training/
│   │   ├── train.py
│   │   ├── baselines.py
│   │   ├── metrics.py
│   │   └── report.py
│   ├── artifacts/               # results.json / results.md / checkpoint
│   └── tests/
│
└── 🖼️ docs/
    └── screenshots/             # images used in this README
```

---

## 🚀 Getting Started

### ✅ Prerequisites

- **Python** 3.10 or newer
- **Node.js** 20 or newer
- A **PostgreSQL** database (a free hosted one such as Neon or Supabase works)

### 1️⃣ Clone the repository

```bash
git clone https://github.com/TanyaVaish-17/recallmate.git
cd recallmate
```

### 2️⃣ Configure environment variables

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql+psycopg://user:password@host/dbname?sslmode=require
JWT_SECRET=replace_with_a_long_random_string
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:5173
VITE_API_URL=http://localhost:8000
```

### 3️⃣ Backend

```bash
cd backend
python -m venv .venv

# Activate the virtual environment
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # macOS / Linux

pip install -r requirements.txt
alembic upgrade head              # create database tables
python -m scripts.seed_demo       # optional: demo data
uvicorn app.main:app --reload
```

- 🌐 API: http://localhost:8000
- 📖 Interactive docs: http://localhost:8000/docs

### 4️⃣ Frontend

Open a **second terminal**:

```bash
cd frontend
npm install
npm run dev
```

- 💻 App: http://localhost:5173

### 🔑 Demo login

After running `python -m scripts.seed_demo`:

| Field | Value |
|---|---|
| 📧 Email | `demo@recallmate.dev` |
| 🔒 Password | `demo12345` |

> The demo account has subjects, topics, questions and exams but **no quiz history and no predictions**.
> Take a few quizzes first, then click **Generate / update plan**.

---

## 🤖 Training the Model

The trained checkpoint (`kt_transformer.pt`) is **not committed** to the repository. Train it from the repo root:

```bash
# 1. install ML dependencies (PyTorch CPU build is fine)
pip install -r ml/requirements.txt

# 2. build the dataset (synthetic students)
python -m ml.data.build_dataset --source synthetic

# 3. train + evaluate
python -m ml.training.train
```

This writes `ml/artifacts/kt_transformer.pt`, `results.json` and `results.md`. Restart the backend afterwards.

To use the real **ASSISTments** dataset instead:

```bash
python -m ml.data.build_dataset --source assistments --csv ml/data/raw/skill_builder_data.csv
python -m ml.training.train
```

> The model needs at least **5 recorded answers** from a student before it produces estimates.

---

## 🔌 API Overview

All routes are prefixed with `/api`. Everything except `auth/register`, `auth/login` and health checks needs a `Bearer` token.

| Area | Endpoints |
|---|---|
| 🔐 **Auth** | `POST /auth/register` · `POST /auth/login` · `GET/PATCH /auth/me` |
| 📚 **Subjects / Topics** | `GET/POST /subjects` · `GET/DELETE /subjects/{id}` · `POST /subjects/{id}/topics` · `DELETE /topics/{id}` |
| 📝 **Exams** | `GET/POST /exams` · `DELETE /exams/{id}` |
| ❓ **Questions** | `POST /topics/{id}/questions` |
| ✅ **Quizzes** | `POST /quizzes/start` · `POST /quizzes/{id}/submit` · `GET /quizzes` · `GET /quizzes/{id}` |
| 📅 **Plan** | `POST /plan/generate` · `GET /plan` · `GET /plan/today` |
| 🗓️ **Sessions** | `POST /plan/sessions` · `POST /plan/sessions/{id}/complete` · `/skip` · `/reschedule` · `DELETE /plan/sessions/{id}` |
| 🤖 **Model** | `GET /model/status` · `GET /model/metrics` · `GET /model/results` · `GET /predictions/topics` |
| 📈 **Analytics** | `GET /analytics/summary` |
| ❤️ **Health** | `GET /health` · `GET /health/db` |

Full request/response schemas are in the Swagger UI at `/docs`.

---

## 🧪 Running Tests

```bash
# Backend (uses in-memory SQLite, never your real database)
cd backend
pip install -r requirements-dev.txt
pytest

# ML pipeline
cd ..
pytest ml
```

---

## 📊 Model Results

> ⚠️ **Synthetic data.** The numbers below come from simulated students. They are a development check, **not**
> results on real students.

| Model | AUC | Accuracy | F1 | Log loss |
|---|---|---|---|---|
| 🤖 Transformer | 0.748 | 0.729 | 0.825 | 0.534 |
| 🤖 Transformer (ids hidden) | 0.703 | 0.703 | 0.817 | 0.561 |
| 📉 Logistic regression | 0.679 | 0.700 | 0.809 | 0.575 |
| 📉 Previous-answer rate | 0.579 | 0.692 | 0.818 | 0.606 |
| 📉 Global rate | 0.500 | 0.692 | 0.818 | 0.617 |

- Split **by student** (700 / 150 / 150), test set evaluated once after model selection
- **"Ids hidden"** is the setting RecallMate uses on its own question bank
- Full details: [`ml/artifacts/results.md`](ml/artifacts/results.md)

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| `ImportError: cannot import name 'model_info'` | Make sure `backend/app/api/routes/model_info.py` exists and `router.py` includes it |
| Dashboard / Plan shows `Not Found` | Backend is missing the routes the frontend calls. Update the backend and restart `uvicorn` |
| `Cannot reach the server` in the browser | Backend isn't running, or `VITE_API_URL` in `.env` is wrong |
| CORS error in the browser console | Add your frontend URL to `CORS_ORIGINS` in `.env` |
| `Model not trained` banner | Train the model, see [Training the Model](#-training-the-model) |
| "Topics needing practice" is empty | Needs a trained model **and** at least 5 recorded quiz answers |
| `uvicorn` not recognised | Use `python -m uvicorn app.main:app --reload` |
| Changes to `.env` ignored | Restart both the backend and `npm run dev` |

---

## 🗺️ Roadmap

- [ ] Train and evaluate on real student data
- [ ] Spaced-repetition baseline to compare against the Transformer
- [ ] Mobile-friendly session reminders
- [ ] Import questions from CSV
- [ ] Docker setup for one-command start

---

<div align="center">

Made with ❤️ by **Tanya Vaish**

⭐ If you found this project useful, consider giving it a star!

</div>