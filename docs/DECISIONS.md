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

## Why the LLM never returns a final score (even per-answer)
- If the model assigns the number, two runs can disagree on the same answer and you can't audit *why* a score moved. So the AI returns only structured dimensions (relevance, understanding, correctness, completeness, reasoning), a status, requirement lists and misconceptions.
- `ScoreEngine` turns those into a 0–10 score with fixed weights and **hard gates** (`irrelevant` ≤ 2.5, `nonsense` ≤ 1.5, misconception-capped ≤ 4.5, contradictory ≤ 4, knowledge gap ≤ 2). The gates are what make an off-topic or keyword-stuffed answer stay low no matter how smooth it sounds.

## Why questions come from a concept bank + planner + LLM (hybrid)
- Pure LLM generation is non-deterministic and can drift; a fixed bank alone can't personalize. The hybrid keeps both: the **concept bank** seeds skills/concepts/rubrics, the **planner** picks what to ask next (skill spread, type rotation, difficulty adaptation, gap targeting), and the **LLM** only writes the question text + rubric, which is validated and deduplicated before it's stored.
- The bank also means the app demos offline (mock provider) with realistic rubrics.

## Why the mock evaluator is behavior-pinned by a benchmark
- The evaluator is the riskiest piece: everything downstream (score, difficulty, report, follow-ups) trusts it. `benchmark_cases.json` (34 cases × 14 categories) pins *behavior* — concise-but-correct = full credit, keyword stuffing = nonsense, irrelevant-but-technical ≤ 2.5, "I don't know" = knowledge gap ≤ 2, contradiction capped, etc. — so a refactor can't silently change grading.

## Why relevance is measured with question-specific topic vocabulary, not generic "technical" words
- "indexes" and "transactions" are technical but they don't answer a decorator question. The mock evaluator builds vocabulary from the question + rubric itself, weights generic tech words at half, treats everything else as noise, and requires a *topic hit* plus noise before flagging an answer irrelevant.
- Synonym/inflection groups on **both** sides (answer and rubric) are why a reworded but correct answer still gets full credit.

## Why misconception matching requires the words in order
- "Defaults are evaluated once at definition time" is a *correct* statement about default arguments, but a naive all-words matcher flags it as "evaluated at call time" — a false accusation that's worse than a miss. Requiring the misconception's content words to appear in the same order (a subsequence) keeps precision high without a large hand-built detector.

## Why follow-ups exist but are strictly bounded
- A partial answer gets a targeted follow-up aimed at the *specific* gap (`_pick_gap`), at equal-or-easier difficulty. The caps keep it coaching, not an interview that grows forever: max depth 2 per chain, one queued follow-up per concept, max 3 follow-ups per interview, and strong/irrelevant/knowledge-gap answers never trigger one.
- An earlier "no follow-ups while ≥3 questions remain unanswered" guard *silently disabled* the feature for standard 5-question interviews — a lesson in same-threshold caps (see README "Lessons Learned").

## Why repeating the question back is its own status ("echo")
- Pasting the question is the cheapest "answer" that can still look on-topic, because a question is built out of its own topic vocabulary — the relevance matcher rewards exactly those words. A user reported it scoring ~6.
- `_is_echo` flags an answer when it re-uses the question's content words in order (or verbatim) while adding almost no new content (`new_ratio ≤ 0.25`). Directive verbs ("explain") are excluded from the question's content words so a trailing "please explain" doesn't defeat it, and answers that add real substance (a full explanation after the paste, or a concise-but-added point) are protected from false flags by the same new-content requirement.
- Echo gets a hard gate (`echo:1.5`) and its own coaching message in the feedback panel, matching how `nonsense` and `knowledge_gap` are treated.

## Why evaluation is now a staged pipeline, not a score formula
- The original evaluator computed relevance → correctness → a weighted score. The pasted-question bug survived that shape because *everything* (relevance, understanding, strengths) was derived from the same topic-vocabulary overlap — an echo of the question maximized it all. No score formula or prompt tweak fixes a structural hole, so the evaluator was rebuilt as a mandatory **Answer Validation** stage that runs *first* and decides status before any credit is computed:

  ```
  validation (gates)  →  relevance  →  understanding  →  correctness  →  question-type  →  status/dimensions
  ```

- The validation stage owns five hard gates, each backed by unit + benchmark cases:
  - **question_repetition** — the question echoed verbatim or lightly paraphrased with ≤ 40% new content (`_is_repetition`, containment/similarity/new-ratio checks against the *question + optional depth points only*). Key insight: expected concepts and core requirements are what a correct answer *must* contain, so reproducing their vocabulary is legitimate answering; only the question itself (and optional follow-up depth points) can be "repeated". Keyword-list copies of the rubric are caught by the stuffing gate instead.
  - **keyword_stuffing** — a short, dense list of rubric keywords with a low prose-to-term ratio, scored on *raw typed* domain tokens so a single legit term like "dictionary" can't inflate itself into a stuffing case.
  - **nonsensical** — long non-words / greeked text.
  - **insufficient_evidence** — on-topic mention-only answers shorter than 4 evidence words (e.g. "dictionary").
  - **irrelevant** — topic density below the relevance threshold.

- **Question type controls evaluation.** Coding questions require code *or* an implementation plan (`_question_type_satisfied`); explanation/comparison/debugging/scenario/system-design questions require their own evidence (comparisons need ≥ 2 expected concepts engaged with ≥ 12 words, even without marker words). This is why "definitions only" to a *coding* question is `incomplete` (demonstrated = []) rather than partial credit.
- **Mention ≠ understanding.** Every stage now distinguishes `mentioned_concepts` from `demonstrated_concepts`; strengths are built *only* from demonstrated concepts, so a candidate can never earn credit just for naming a topic.
- **Similarity is never scored as correctness.** High similarity to the question now means *repetition* (a hard 1-point cap), never credit.
- Statuses carry deterministic score caps (`status_score_caps`): `question_repetition:1`, `keyword_stuffing:1`, `insufficient_evidence:2`, `irrelevant:2`, `incomplete:6`, `partial:7`, `strong:10`, etc. Gates are non-negotiable — a gated status can never be overridden by a high similarity/completeness score.

## Why the scoring dimensions are surfaced verbatim in the UI
- Coaching-first feedback (demonstrated / partial / missing / corrections, with the score demoted to a badge) is what a candidate can actually act on. The structured fields are returned by the API (`AnswerSubmissionResponse`) and rendered directly, so the frontend never re-derives what the evaluator concluded.

---

## Part 50.5 — Answer-Validation Refactor (the pasted-question bug)

**Goal achieved:** pasted/paraphrased questions, keyword mentions, and question-type-inappropriate answers can *never* earn credit again, at the architecture level.

**Root cause.** The mock evaluator built its topic vocabulary from `question + expected_concepts + core_requirements`. Pasting the question therefore produced 100% topic-vocabulary overlap → relevance ≈ 10 → `partial` ≈ 6.2 credit; there was no validation stage, mentioning a concept scored it as demonstrated, question type was ignored, and strengths were minted from mere mentions.

**Fix.** A mandatory validation stage first (`_validate_answer`), 11 statuses (was 4), the `mentioned` vs `demonstrated` concept split (persisted via migration `f04063a038bb`), per-question-type evidence requirements, and status score caps that gates can never be outvoted past. Full detail in "Why evaluation is now a staged pipeline" above.

**Verification.** 90 pytest tests (incl. 10 new `test_answer_validation.py` acceptance tests and rewritten behavior tests) + a 46-case behavioral benchmark all pass; `ruff check app tests` clean. The 10 acceptance scenarios (paste → repetition, light paraphrase → repetition, keyword list → stuffing, single word → insufficient evidence, short complete comparison → strong, bread sentence → irrelevant, wrong-but-grammatical → incorrect, synonymous terminology → strong, partial-with-gap → partial, definitions-only to coding → incomplete) are pinned both in the benchmark and as pytest tests.

---

## Part 50 — Final Summary

**Goal achieved:** the app is no longer a static question-answerer — it is an **adaptive
coach**. Over the final 24 parts (Parts 27–50) the evaluation and question-generation
pipeline was rebuilt and the frontend reworked around coaching:

**Pipeline (question side).** Hybrid generation: concept bank → planner (skill spread,
type rotation, difficulty adaptation, gap targeting) → LLM → validation (answerability +
bank consistency + similarity dedup + seed fallback) → database. Questions now carry a
full rubric (expected concepts, core requirements, optional depth points, common
misconceptions, intent).

**Pipeline (answer side).** The AI returns structured dimensions only; `ScoreEngine`
scores deterministically with weights (.25/.25/.2/.2/.1) and hard status gates. The mock
evaluator gained topic-density relevance, two-sided synonym/stem matching, ordered
misconception detection, contradiction-before-relevance ordering, and a keyword-stuffing
detector. Partial/weak answers produce a targeted, difficulty-lowered follow-up
(depth ≤ 2, ≤ 3 per interview, 1 per concept).

**Frontend.** Coaching-first feedback panel: demonstrated / partially covered / not yet
covered / corrections, with the score as a secondary badge; follow-up questions are
surfaced inline with an "Answer follow-up" path and preferred by "Next question".

**Verification.** 77 pytest tests (incl. 12 evaluator-behavior tests) + a 34-case
behavioral benchmark (`python scripts/run_benchmark.py`) all pass; `ruff check app tests`
clean; the full flow was exercised live against PostgreSQL with the mock provider
(follow-up created → queued → answered → depth cap stops the chain).

**Bugs the live run caught:** a `VARCHAR(40)` `intent` column truncated planner intents
(fixed by widening to 255 via migration `f04063a037ca`), and the follow-up guard that
disabled follow-ups on 5-question interviews (fixed by a total-follow-ups cap). Both are
now regression-proof: the migration is applied and the planner behavior is exercised by
the API-level follow-up tests.
