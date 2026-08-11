# Design Decisions — Why We Built It This Way

Short, beginner-friendly explanations of every major architectural choice.
Read this after the README to understand *why*, not just *what*.

---

## Why FastAPI?
- **Modern, fast, async-ready** Python web framework with automatic interactive docs at `/docs`.
- **First-class Pydantic support**: request/response validation is built-in, so bad input is rejected with a 422 before it reaches your code.
- **Dependency injection** (via `Depends`) makes auth, DB sessions and the AI service easy to share and easy to override in tests.
- Compare: Django is heavier (full framework); Flask needs you to wire up validation yourself.

## Why PostgreSQL?
- Relational data (users → interviews → questions → answers → evaluations) fits a relational DB perfectly.
- Real `FOREIGN KEY` and `UNIQUE` constraints enforce data integrity — this project caught a real bug *only* on PostgreSQL (see README "Production bugs caught").
- Free, industry-standard, supported everywhere (Render, Railway, Supabase, Neon, RDS...).
- SQLite is used only for tests and quick local runs because it needs zero setup.

## Why SQLAlchemy (ORM)?
- Maps Python classes to tables, removing repetitive SQL string-writing.
- **DB-agnostic**: the same model code works on PostgreSQL and SQLite, so tests can run in-memory without a database server.
- Relationships (`interview.questions`, `question.answer`) make traversing related rows natural.
- We also run **Alembic migrations** on top so schema changes are versioned and repeatable — you never hand-edit a production database.

## Why a service layer (Router → Service → Database/AI)?
- Routers should only handle HTTP (parse request, format response).
- Business rules live in services, which are **plain Python classes you can call and test without HTTP**.
- If you later add another API (GraphQL, CLI, webhook) the logic is already reusable.
- It keeps each function small and readable.

## Why Pydantic for schemas AND for AI output?
- Schemas: validated boundaries between the client and your code (auto 422 on bad input).
- AI output: LLMs are unreliable — they can return wrong types, missing keys, or nonsense. Validating with Pydantic means a bad response fails loudly and predictably instead of silently corrupting the database.

## Why JWT for auth?
- Stateless: the server verifies a signed token without storing session rows, so it scales trivially and works across multiple API servers.
- The token is signed with a secret key (`SECRET_KEY`), so clients can't forge it.
- Password hashing with **bcrypt** (salted, computationally expensive) means even a leaked database doesn't reveal plaintext passwords.

## Why a single AI abstraction (`AIService`)?
- The rest of the app calls `ai.analyze_candidate()`, `ai.generate_questions()`, `ai.evaluate_answer()`, `ai.generate_report()`.
- Nobody else knows (or cares) whether the provider is OpenAI, a local model, or the offline mock.
- Benefits:
  - **Swap providers** by changing env vars — no code changes.
  - **Test without the network**: tests inject a fake implementation.
  - **Handle failures in one place**: timeout/retry/JSON-parsing logic lives in `LLMService`.

## Why mock the LLM in tests?
- Tests must be fast, deterministic, and free.
- A real API call is slow, costs money, and can fail for reasons unrelated to your code.
- `ControllableAIService` returns exact, scripted outputs (including error cases), so tests can check *your* logic precisely — not the LLM's.

## Why rule-based adaptive difficulty instead of ML?
- The requirement is tiny: bump difficulty after a great answer, lower it after a weak one.
- A deterministic 3-line rule (`score >= 8 → up`, `5–8 → same`, `< 5 → down`) is **transparent, debuggable, and testable**. ML would be over-engineering with zero benefit here.
- It's documented in the code (`EvaluationService.adapt_difficulty`) so a reviewer can verify it in seconds.

## Why Docker?
- One command (`docker compose up --build`) runs Postgres + API + frontend on any machine — no "works on my machine" problems.
- The image includes everything the app needs (dependencies, config, migrations).
- It's the standard way deployments and CI test the same artifact you run locally.

## Why GitHub Actions?
- CI runs your tests and build on every push/PR automatically.
- It enforces a quality bar: broken code can't quietly merge.
- The pipeline here runs backend tests, a frontend build, and a Docker build.

## Why JSON columns for lists (strengths, skills, topics)?
- These are unstructured, variable-length lists without relationships or queries. Storing them as JSON is the simplest correct fit.
- The only aggregation we need (skill scores) is computed in Python at report time and stored in the relational `skill_scores` table.
- If you later need "find all interviews mentioning Docker," a proper junction table would be the upgrade — that's intentionally out of scope for an MVP.

## Why score math is NOT done by the LLM
- Numbers must be reproducible and auditable. So overall and per-skill scores are computed deterministically from stored evaluations.
- The LLM only writes the qualitative narrative (summary, strengths, weaknesses, recommendations). Best of both worlds: deterministic math + rich language.
