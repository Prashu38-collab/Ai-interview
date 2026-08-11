# AI Interviewer — Planning Document (Phase 1)

## 1. Project Overview

**AI Interviewer** is a web application that runs automated, personalized **technical
interviews** for software engineering candidates. A candidate pastes their **resume**
and a **job description**, picks a **target role** and **experience level**, and the
system:

1. Analyzes resume + job description to find skills, requirements and gaps.
2. Generates personalized interview questions.
3. Presents the interview one question at a time in a web UI.
4. Evaluates each written answer with an LLM, assigning a score (0–10) and feedback.
5. Adapts question difficulty based on performance (rule-based, no ML).
6. Produces a final report: overall score, skill-wise scores, strengths, weaknesses,
   and recommended learning topics.

**Why build it:** It demonstrates the full software lifecycle (planning → architecture →
AI integration → database → API → frontend → testing → Docker → CI/CD → deployment →
docs) in one small, understandable project. It is deliberately NOT an enterprise
system — it is a polished, working MVP sized for ~2 days of work.

## 2. Functional Requirements

**Auth**
- Register with email + password (hashed).
- Login with email + password → JWT token.
- Get current user profile.

**Interviews**
- Create an interview: target role, experience level, job description, resume text,
  optional duration, optional number of questions.
- Analyze resume + job description (AI) → skills, gaps, topics.
- Generate questions (AI) → stored per interview, no duplicates.
- Retrieve questions for an interview.

**Interview flow**
- Start an interview, answer one question at a time.
- Submit an answer → AI evaluation (score, strengths, weaknesses, feedback, missing concepts).
- Adaptive difficulty after each evaluation (rule-based).
- Complete the interview → generate final report (overall score, skill scores, etc.).

**Frontend**
- Pages: `/login`, `/register`, `/dashboard`, `/interviews/new`, `/interviews/:id`,
  `/interviews/:id/report`.
- Loading / error / empty states.

## 3. Non-Functional Requirements

- **Testability:** Tests run without any external LLM call (AI is mocked).
- **Resilience:** The app never crashes if the LLM fails; graceful app-level errors.
- **Security:** JWT auth, bcrypt password hashing, per-user data isolation, env vars,
  CORS config, no hard-coded secrets.
- **Portability:** Runs via `docker compose up --build` or bare-metal (FastAPI + uvicorn).
- **Simplicity:** No microservices, no Kubernetes, no message brokers, no vector DBs.

## 4. User Stories

1. As a candidate, I can register/login so my interviews are private.
2. As a candidate, I can create an interview from my resume and a job description.
3. As a candidate, I can let the AI analyze my resume against the job description
   and see recommended topics.
4. As a candidate, I can get personalized interview questions.
5. As a candidate, I can answer questions one at a time and get instant feedback.
6. As a candidate, I can see a final report with skill-wise scores and recommendations.
7. As a candidate, I can only see my own interviews and reports.

## 5. System Architecture

```
Browser (React + Vite + Tailwind)
        │  HTTP/JSON (JWT in Authorization header)
        ▼
FastAPI (REST API)
   │  routers  →  services  →  (models / AI)
   ▼                │
  Services          └──▶ AI Service
   │                      ├── Prompt Service (templates → JSON)
   │                      ├── LLM Service (provider call, retries, parsing)
   │                      └── Pydantic validation of AI output
   ▼
SQLAlchemy ORM  ──▶  PostgreSQL  (SQLite in tests only)
```

Key principle: **Router → Service → Database/AI.** Routers contain no business logic.
All LLM usage flows through a single `AIService` abstraction so the LLM provider is
swappable and testable.

## 6. Database ER Design

```
users (id, email UNIQUE, full_name, hashed_password, created_at)
  │ 1
  │ N
interviews (id, user_id FK, target_role, experience_level, job_description,
            resume_text, number_of_questions, duration_minutes,
            analysis JSON, status, created_at, updated_at)
  │ 1
  │ N
questions (id, interview_id FK, text, skill, difficulty, question_type,
           expected_concepts JSON, order_index, status)
  │ 1
  │ 1
answers (id, question_id FK, text, created_at)
  │ 1
  │ 1
evaluations (id, answer_id FK, score, strengths JSON, weaknesses JSON,
             feedback, missing_concepts JSON, model_used, created_at)

interviews 1 ─── 1 interview_reports (id, interview_id FK UNIQUE, overall_score,
             average_score, summary, strengths JSON, weaknesses JSON,
             recommendations JSON, created_at)

interview_reports 1 ─── N skill_scores (id, report_id FK, skill, score,
             question_count)
```

JSON columns store list data (skills, strengths, etc.) to keep the schema simple.
The report aggregates evaluations at completion time (nothing duplicated).

## 7. API Design

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/auth/register` | – | Create account |
| POST | `/auth/login` | – | Get JWT |
| GET | `/auth/me` | ✅ | Current user |
| POST | `/interviews` | ✅ | Create interview |
| GET | `/interviews` | ✅ | List my interviews |
| GET | `/interviews/{id}` | ✅ | Interview detail |
| POST | `/interviews/{id}/analyze` | ✅ | AI analyze resume+JD |
| POST | `/interviews/{id}/generate-questions` | ✅ | AI generate questions |
| GET | `/interviews/{id}/questions` | ✅ | List questions |
| POST | `/questions/{id}/answer` | ✅ | Submit + evaluate answer |
| POST | `/interviews/{id}/complete` | ✅ | Finalize + build report |
| GET | `/interviews/{id}/report` | ✅ | Fetch report |

Error model: `{"detail": "message"}` (FastAPI default). 404 for missing resources,
403 for cross-user access, 401 for bad credentials, 422 for validation.

## 8. Folder Structure

```
backend/
  app/
    main.py                  # FastAPI app factory, CORS, router mounting
    core/config.py           # pydantic-settings (env vars)
    core/security.py         # bcrypt + JWT helpers
    db/database.py           # engine, session, Base
    models/                  # SQLAlchemy models
      user.py interview.py question.py answer.py evaluation.py report.py
    schemas/                 # Pydantic request/response schemas
      auth.py interview.py question.py answer.py evaluation.py report.py common.py
    routers/
      auth.py interviews.py questions.py answers.py reports.py deps.py
    services/
      auth_service.py interview_service.py question_service.py
      evaluation_service.py report_service.py
      ai/
        base.py              # AIService abstract base + AI result models
        prompt_service.py    # builds prompts from templates
        llm_service.py       # provider transport (OpenAI-compatible), retries/parsing
        ai_service.py        # AIService impl: analyze/generate/evaluate/report
    prompts/interview_prompts.py
  alembic/                   # migrations (alembic init)
  tests/                     # pytest suite (AI mocked)
  requirements.txt  .env.example  Dockerfile
frontend/
  src/
    api/client.js  auth.js  interviews.js
    components/  Layout.jsx  QuestionCard.jsx  Loading.jsx  ErrorBox.jsx ...
    pages/  Login.jsx Register.jsx Dashboard.jsx NewInterview.jsx
            Interview.jsx Report.jsx
    App.jsx  main.jsx  index.css
  package.json  vite.config.js  Dockerfile
docker-compose.yml
.env.example
.github/workflows/ci.yml
README.md
```

## 9. Development Milestones

| # | Milestone | Exit criteria |
|---|-----------|---------------|
| M0 | Skeleton + git init | Empty project commits cleanly |
| M1 | Core/DB/models/Alembic | Migrations generate + apply |
| M2 | Auth | register/login/me tested |
| M3 | AI abstraction + prompts | AIService with mock provider |
| M4 | Interview + analysis | create + analyze endpoints |
| M5 | Question generation | questions stored, no dupes |
| M6 | Answer + evaluation + adaptive difficulty | scores adapt difficulty |
| M7 | Report | complete + report endpoints |
| M8 | Tests | 15–25 passing tests, no API calls |
| M9 | Frontend | full interview flow in browser |
| M10 | Docker | `docker compose up --build` works |
| M11 | CI | GitHub Actions green |
| M12 | Docs | README complete |

## 10. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| No LLM API key during dev | AI endpoints fail | Mock provider + graceful errors; `.env.example` documents setup; **MockLLMService** for local dev |
| LLM returns bad JSON | Evaluation breaks | Strict Pydantic validation + repair/retry + fallback defaults |
| Time budget (2 days) | Scope creep | Hard P0 scope; no microservices/ML/voice |
| Postgres not available locally | Migrations fail | SQLite fallback via `DATABASE_URL` (SQLite for tests only) |
| Frontend build complexity | Deadline miss | Minimal Tailwind UI, no heavy animation libs |

---

**Decision log / teaching notes** (short, per request §28) is maintained in
`docs/DECISIONS.md` as we implement.
