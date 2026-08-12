"""Deterministic, offline implementation of :class:`AIService`.

Purpose:
- Lets the whole app run and be demoed without any API key
  (set ``LLM_PROVIDER=mock``, which is the default).
- Makes automated tests fast and reliable: no network, no flakiness.

Questions come from the curated concept bank (see ``concept_bank.py``): the
planner picks a concept + question type, and the mock builds the question and
its rubric from the concept's seed questions and key points. Evaluation is
heuristic but structured: it detects off-topic answers, keyword stuffing,
knowledge gaps, and known misconceptions, and produces the same
:class:`EvaluationDimensions` the real LLM service produces, so the whole app
pipeline (score engine, feedback, planner follow-ups) runs identically.

Known limitation: mock "understanding" is keyword/coverage-based, not semantic.
It does cover synonyms and common inflections (see ``SYNONYM_GROUPS``), but a
truly reworded answer may still under-score. The real LLM provider does genuine
semantic evaluation.
"""

import re

from app.services.ai.base import (
    AIService,
    CandidateAnalysis,
    EvaluationDimensions,
    QuestionData,
    QuestionPlanSlot,
    ReportSummary,
)
from app.services.ai.concept_bank import FOLLOWUP_STARTERS, normalize_type

# skill -> substrings that indicate the skill appears in a text (case-insensitive)
SKILL_KEYWORDS: dict[str, list[str]] = {
    "Python": ["python", "django", "flask", "fastapi", "pandas", "asyncio", "pytest"],
    "FastAPI": ["fastapi", "pydantic"],
    "PostgreSQL": ["postgres", "postgresql", "sql", "database", "alembic"],
    "Docker": ["docker", "container"],
    "REST APIs": ["rest", "api", "endpoint", "http"],
    "React": ["react", "javascript", "frontend"],
    "Testing": ["test", "pytest", "unittest", "jest"],
    "Git": ["git", "github"],
    "AWS": ["aws", "s3", "ec2", "lambda", "cloud"],
}

# Words that signal technical substance. Used by the mock evaluator: a word
# counts as "relevant" if it is in this glossary or tied to the question's
# skill/concept. Words that are neither relevant nor stopwords are noise
# (e.g. "snake", "animals") and pull the score down.
TECH_TERMS = {
    "python", "programming", "programmer", "language", "code", "codes",
    "coding", "script", "scripts", "interpreter", "interpreted", "compile",
    "compiled", "runtime", "library", "libraries", "framework", "frameworks",
    "syntax", "function", "functions", "class", "classes", "object",
    "objects", "method", "methods", "variable", "variables", "loop", "loops",
    "iteration", "iterating", "recursion", "recursive", "algorithm",
    "algorithms", "data", "database", "databases", "sql", "query", "queries",
    "api", "apis", "rest", "endpoint", "endpoints", "http", "server",
    "servers", "client", "clients", "request", "requests", "response",
    "responses", "json", "web", "backend", "frontend", "service", "services",
    "microservice", "microservices", "thread", "threads", "process",
    "processes", "memory", "performance", "optimize", "optimizing",
    "optimization", "optimized", "scalability", "scale", "scaling",
    "concurrency", "concurrent", "async", "asynchronous", "coroutine",
    "coroutines", "event", "error", "errors", "exception", "exceptions",
    "debugging", "debug", "test", "tests", "testing", "tested", "pytest",
    "unittest", "jest", "deployment", "deploy", "deployed", "docker",
    "container", "containers", "kubernetes", "cloud", "aws", "automation",
    "automate", "automated", "automating", "machine", "learning", "artificial",
    "intelligence", "neural", "network", "networks", "model", "models",
    "git", "version", "control", "schema", "schemas", "migration",
    "migrations", "fastapi", "django", "flask", "pandas", "react",
    "javascript", "typescript", "html", "css", "postgres", "postgresql",
    "alembic", "sqlalchemy", "pydantic", "redis", "cache", "caching",
    "authentication", "authorization", "token", "tokens", "jwt", "oauth",
    "graphql", "websocket", "websockets", "security", "encryption",
    "monitoring", "logging", "metrics", "pipeline", "pipelines", "workflow",
    "workflows", "repository", "latency", "throughput", "queue", "queues",
    "message", "messages", "streaming", "streams", "batch", "scheduler",
    "cron", "profiler", "profiling", "bottleneck", "bottlenecks", "mutex",
    "deadlock", "transaction", "transactions", "acid", "mvcc", "index",
    "indexes", "indices", "normalization", "production", "system", "systems",
    "architecture", "design", "designed", "designing", "solution", "solutions",
    "example", "examples", "development", "develop", "developer",
    "developers", "developing", "processing", "science",
    "scientific", "build", "builds", "building", "built", "write", "writes",
    "writing", "written", "wrote", "staging", "load", "traffic",
    "failure", "failures", "reliability", "availability", "efficiency",
    "efficient", "versioning", "collaboration", "review", "reviews", "sync",
    # Core Python / CS domain words. These also let the keyword-stuffing
    # detector recognise dense technical vocabulary that isn't generic.
    "decorator", "decorators", "wrapper", "wrappers", "callable", "callables",
    "functools", "metaclass", "generator", "generators", "closure", "closures",
    "lambda", "wraps", "wrapping", "wrapped", "return", "returns", "returned",
    "yield", "yields", "iterator", "iterators", "list", "lists", "dict",
    "tuple", "set", "sets", "mutable", "immutable", "dynamically", "typed",
}

# Neutral filler: common function words, generic verbs and vague adjectives.
# These are ignored by the noise detector so only genuinely off-topic words
# (e.g. "snake", "animals", "weather") drag the score down.
STOPWORDS = {
    "this", "that", "these", "those", "with", "have", "has", "had", "from",
    "their", "they", "about", "which", "there", "when", "what", "where",
    "were", "been", "will", "would", "could", "should", "into", "than", "then",
    "them", "over", "under", "such", "used", "using", "use", "uses", "thing",
    "things", "stuff", "very", "just", "because", "also", "some", "other",
    "being", "does", "doing", "did", "make", "made", "makes", "making", "get",
    "got", "gotten", "give", "gave", "given", "giving", "like", "every",
    "more", "most", "each", "any", "can", "able", "after", "before", "even",
    "much", "many", "one", "two", "way", "ways", "really", "basically",
    "kind", "sort", "right", "everywhere", "everything", "always", "sometimes",
    "often", "usually", "overall", "obviously", "actually", "instead",
    "someone", "something", "anyone", "anything", "sure", "maybe", "perhaps",
    "need", "needs", "wants", "want", "know", "knows", "good", "great", "bad",
    "work", "works", "working", "job", "jobs", "whatever", "whether", "either",
    "neither", "both", "only", "while", "since", "run", "runs", "running",
    "ran", "rely", "relies", "relying", "schedule", "schedules", "scheduled",
    "allow", "allows", "allowed", "enables", "enable", "enabled", "help",
    "helps", "helped", "helping", "call", "calls", "called", "calling", "take",
    "takes", "taken", "show", "shows", "showed", "shown", "handle", "handles",
    "handled", "easy", "hard", "simple", "complex", "important", "useful",
    "main", "key", "best", "top", "lot", "lots", "bit", "rather", "quite",
    "fairly", "pretty", "several", "various", "different", "same", "similar",
    "better", "worse", "little", "big", "large", "small", "high", "low",
    "few", "number", "part", "parts", "type", "types",
    "new", "old", "first", "last", "next", "well", "though",
    "although", "however", "therefore", "plus", "minus", "without", "within",
    "along", "during", "among", "through", "across", "around", "below",
    "above", "near", "far", "away", "back", "forth", "here",
    "level", "levels", "widely", "broadly", "commonly", "typically",
    # Basic function words. These are never content words, so they cannot
    # inflate an off-topic answer's relevance ("the sky is blue and...") or pad
    # out a rubric requirement's content-word list.
    "a", "an", "all", "and", "are", "as", "at", "be", "but", "by", "do",
    "for", "how", "i", "if", "in", "is", "it", "its", "me", "my", "no",
    "nor", "not", "of", "on", "or", "our", "out", "so", "the", "to", "us",
    "via", "was", "we", "who", "whom", "why", "you", "your", "yours",
    "he", "she", "him", "her", "his",
    "please", "pls", "kindly", "thanks", "thank", "thx",
}

# Phrases that signal "I don't know" (a knowledge gap, not a wrong answer).
KNOWLEDGE_GAP_PATTERNS = (
    "don't know", "do not know", "i'm not sure", "am not sure", "not sure",
    "haven't learned", "have not learned", "haven't studied", "haven't worked",
    "have not worked", "not familiar", "no idea", "not studied", "never learned",
    "i don't remember", "not yet covered",
)

# Small contradiction detector (mock-grade): a phrase from each side -> contradiction.
CONTRADICTION_PAIRS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("always",), ("never",)),
    (("increases",), ("decreases",)),
    (("can change",), ("cannot change",)),
    (("is thread-safe",), ("is not thread-safe",)),
    (("strong consistency",), ("eventual consistency",)),
)

# Mock-grade synonym groups: words the evaluator treats as the same concept.
# This lets a concise answer earn full credit even when it avoids the exact
# wording of the rubric (e.g. "returns a wrapper" for "wraps a callable").
SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"call", "calls", "called", "calling", "callable", "function",
               "functions", "method", "methods", "routine", "routines"}),
    frozenset({"wrap", "wraps", "wrapped", "wrapping", "wrapper", "wrappers"}),
    frozenset({"modify", "modifies", "modified", "modifying", "change",
               "changes", "changed", "changing", "alter", "alters"}),
    frozenset({"execute", "executes", "executed", "executing", "run", "runs",
               "running", "ran", "invoke", "invokes", "invoked"}),
    frozenset({"store", "stores", "stored", "storing", "persist", "persists",
               "persisted", "persisting", "cache", "caches"}),
    frozenset({"return", "returns", "returned", "returning", "yield",
               "yields"}),
    frozenset({"query", "queries", "fetch", "fetches", "retrieve",
               "retrieves", "search", "searches"}),
    frozenset({"thread", "threads", "process", "processes", "concurrent",
               "concurrency", "parallel", "parallelism"}),
)

# Thresholds
STUFFING_TECH_RATIO = 0.6
STUFFING_MAX_WORDS = 14
IRRELEVANT_RELEVANCE = 0.5


def _scan_skills(text: str) -> list[str]:
    lower = text.lower()
    return [skill for skill, keywords in SKILL_KEYWORDS.items() if any(k in lower for k in keywords)]


class MockAIService(AIService):
    name = "mock"

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------
    def analyze_candidate(
        self,
        *,
        target_role: str,
        experience_level: str,
        job_description: str,
        resume_text: str,
    ) -> CandidateAnalysis:
        candidate_skills = _scan_skills(resume_text)
        required_skills = _scan_skills(job_description) or _scan_skills(target_role)
        skill_gaps = [s for s in required_skills if s not in candidate_skills]
        topics = (required_skills + [s for s in candidate_skills if s not in required_skills])[:6]
        return CandidateAnalysis(
            candidate_skills=candidate_skills,
            required_skills=required_skills,
            skill_gaps=skill_gaps,
            topics=topics or ["Core Programming", "Problem Solving"],
        )

    # ------------------------------------------------------------------
    # Question generation (bank-driven)
    # ------------------------------------------------------------------
    def generate_questions(
        self,
        *,
        target_role: str,
        experience_level: str,
        analysis: CandidateAnalysis,
        number: int,
        difficulty: str,
        previous_questions: list[str],
        previous_concepts: list[str],
        plan: list[QuestionPlanSlot] | None = None,
    ) -> list[QuestionData]:
        slots = plan or self._default_plan(analysis.topics, number, difficulty)
        from app.services.question_validator import QuestionValidator

        validator = QuestionValidator()
        used_texts: set[str] = set(previous_questions)
        out: list[QuestionData] = []
        for slot in slots[:number]:
            qdata = validator.build_from_slot(slot)
            # If a seed for this (concept, type) was already used, try other
            # types before skipping the slot entirely.
            if qdata.question in used_texts:
                swapped = False
                for _ in range(3):
                    slot = slot.model_copy(
                        update={"question_type": _rotate_type(slot.question_type)}
                    )
                    qdata = validator.build_from_slot(slot)
                    if qdata.question not in used_texts:
                        swapped = True
                        break
                if not swapped:
                    continue
            used_texts.add(qdata.question)
            out.append(qdata)
        return out[:number]

    @staticmethod
    def _default_plan(topics: list[str], number: int, difficulty: str) -> list[QuestionPlanSlot]:
        """Fallback plan when the service did not pass one."""
        slots: list[QuestionPlanSlot] = []
        for i in range(number):
            skill = topics[i % len(topics)] if topics else "Core Programming"
            slots.append(
                QuestionPlanSlot(
                    skill=skill,
                    concept=skill,
                    difficulty=difficulty,
                    question_type=["explanation", "scenario", "coding"][i % 3],
                    intent="explore the concept",
                )
            )
        return slots

    # ------------------------------------------------------------------
    # Answer evaluation (structured, heuristic)
    # ------------------------------------------------------------------
    def evaluate_answer(
        self,
        *,
        question_text: str,
        skill: str,
        concept: str | None,
        difficulty: str,
        question_type: str,
        intent: str | None,
        expected_concepts: list[str],
        core_requirements: list[str],
        optional_depth_points: list[str],
        common_misconceptions: list[str],
        answer_text: str,
    ) -> EvaluationDimensions:
        words = re.findall(r"[a-z']+", answer_text.lower())
        distinct = set(words)
        word_count = len(words)

        # --- I don't know ---------------------------------------------------
        if _is_knowledge_gap(answer_text):
            return EvaluationDimensions(
                answer_status="knowledge_gap",
                relevance_score=0.5,
                understanding_score=0,
                correctness_score=0,
                completeness_score=0,
                reasoning_score=0,
                missing_requirements=list(core_requirements),
                recommended_topics=[concept or skill],
                confidence=0.9,
                strengths=["Was honest about not knowing."],
            )

        # --- echo: repeating the question is not an answer ------------------
        # Pasting the question back is made of the question's own topic
        # vocabulary, so without this guard it looks fully on-topic and scores
        # mid-range despite containing no answer at all.
        if _is_echo(question_text, answer_text, words):
            return EvaluationDimensions(
                answer_status="echo",
                relevance_score=2.0,
                understanding_score=0.5,
                correctness_score=0.5,
                completeness_score=0,
                reasoning_score=0,
                missing_requirements=list(core_requirements),
                recommended_topics=[concept or skill],
                confidence=0.9,
                strengths=[],
            )

        # --- topic vocabulary ------------------------------------------------
        topic_words: set[str] = set()
        for phrase in [skill, concept or "", question_text] + expected_concepts + core_requirements:
            topic_words.update(_content_words(phrase))
        topic_vocab = _expand_terms(topic_words)
        relevant_vocab = _expand_terms(set(TECH_TERMS)) | topic_vocab

        # An answer is on-topic when it engages THIS question's concept words,
        # not just any technical vocabulary ("indexes/transactions" don't answer
        # a decorator question). Generic tech words still contribute, but with
        # half the weight. Both sides are synonym/inflection-expanded, so
        # "begins" counts for a rubric that says "begin".
        expanded_present = _expand_terms(distinct)
        topic_hits = expanded_present & topic_vocab
        relevant_vocab = _expand_terms(set(TECH_TERMS)) | topic_vocab
        tech_hits = (expanded_present & relevant_vocab) - topic_hits
        noise = {
            w
            for w in distinct
            if len(w) >= 4
            and w not in STOPWORDS
            and _word_group(w).isdisjoint(relevant_vocab)
        }
        meaningful = len(topic_hits) + len(tech_hits) + len(noise)
        relevance_ratio = (
            (len(topic_hits) + 0.5 * len(tech_hits)) / meaningful if meaningful else 0.0
        )
        topic_density = (
            len(topic_hits) / (len(topic_hits) + len(noise))
            if (topic_hits or noise)
            else 0.0
        )

        # --- keyword stuffing / nonsense ------------------------------------
        # A dense burst of domain words with no connecting language is not an
        # answer. Domain words = glossary OR this question's own vocabulary.
        domain_terms = {w for w in distinct if w in TECH_TERMS or w in topic_vocab}
        glue = {w for w in distinct if w in STOPWORDS}
        stuffing = (
            len(domain_terms) >= 4
            and len(glue) == 0
            and word_count <= STUFFING_MAX_WORDS
            and len(domain_terms) / max(word_count, 1) >= STUFFING_TECH_RATIO
        )
        if stuffing:
            return EvaluationDimensions(
                answer_status="nonsense",
                relevance_score=3.0,
                understanding_score=0.5,
                correctness_score=0.5,
                completeness_score=0,
                reasoning_score=0,
                missing_requirements=list(core_requirements),
                recommended_topics=[concept or skill],
                confidence=0.9,
                strengths=[],
            )

        # --- rubric requirement matching ------------------------------------
        satisfied, partial, missing = _requirements_state(
            core_requirements,
            words,
            topic_hits=topic_hits,
            noise=noise,
            word_count=word_count,
        )
        total = len(core_requirements) or 1
        coverage = (len(satisfied) + 0.5 * len(partial)) / total

        # --- misconceptions & contradictions --------------------------------
        # Checked BEFORE the relevance gate: an answer that states a known
        # misconception or contradicts itself is a stronger signal than its
        # token-level relevance ratio.
        misconceptions = _detect_misconceptions(common_misconceptions, answer_text)
        contradictions = _detect_contradictions(answer_text)
        if contradictions:
            return self._dims_for(
                status="contradictory",
                relevance_ratio=relevance_ratio,
                topic_density=topic_density,
                coverage=coverage,
                word_count=word_count,
                satisfied=satisfied,
                partial=partial,
                missing=missing,
                concept=concept or skill,
                skill=skill,
                question_type=normalize_type(question_type),
                contradictions=contradictions,
                technical_errors=misconceptions,
            )
        if misconceptions:
            return self._dims_for(
                status="incorrect",
                relevance_ratio=relevance_ratio,
                topic_density=topic_density,
                coverage=coverage,
                word_count=word_count,
                satisfied=satisfied,
                partial=partial,
                missing=missing,
                concept=concept or skill,
                skill=skill,
                question_type=normalize_type(question_type),
                technical_errors=misconceptions,
            )

        # --- relevance gate -------------------------------------------------
        if not topic_hits and noise:
            return EvaluationDimensions(
                answer_status="irrelevant",
                relevance_score=round(10 * relevance_ratio, 1),
                understanding_score=round(10 * relevance_ratio, 1),
                correctness_score=2.0,
                completeness_score=0,
                reasoning_score=round(5 * relevance_ratio, 1),
                missing_requirements=list(core_requirements),
                recommended_topics=[concept or skill],
                confidence=0.85,
                strengths=[],
            )

        # --- partial vs on-topic --------------------------------------------
        status = "on_topic" if coverage >= 0.8 else "partial"
        return self._dims_for(
            status=status,
            relevance_ratio=relevance_ratio,
            topic_density=topic_density,
            coverage=coverage,
            word_count=word_count,
            satisfied=satisfied,
            partial=partial,
            missing=missing,
            concept=concept or skill,
            skill=skill,
            question_type=normalize_type(question_type),
        )

    # ------------------------------------------------------------------
    def _dims_for(
        self,
        *,
        status: str,
        relevance_ratio: float,
        coverage: float,
        word_count: int,
        satisfied: list[str],
        partial: list[str],
        missing: list[str],
        concept: str,
        skill: str,
        question_type: str,
        contradictions: list[str] | None = None,
        technical_errors: list[str] | None = None,
        topic_density: float | None = None,
    ) -> EvaluationDimensions:
        # A short answer can be relevant but it cannot be *highly* relevant, and
        # an incomplete answer should not get near-full correctness credit.
        length_factor = min(1.0, word_count / 10 + 0.2)
        density = topic_density if topic_density is not None else relevance_ratio
        relevance_score = round(
            10 * min(1.0, 0.5 * density + 0.5 * relevance_ratio) * length_factor, 1
        )
        completeness_score = round(10 * coverage, 1)
        understanding_score = round(10 * min(1.0, coverage * 0.75 + min(word_count / 40, 0.25)), 1)
        if coverage >= 0.8:
            correctness = 7.5
        else:
            correctness = round(2.0 + 5.5 * (coverage / 0.8), 1)
        if technical_errors:
            correctness = max(2.0, correctness - 2.5 * len(technical_errors))
        if contradictions:
            correctness = max(2.0, correctness - 2.0)
        reasoning_score = round(10 * min(1.0, relevance_ratio * min(word_count / 12, 1.0)), 1)

        gap = _pick_gap(missing, partial, concept)
        follow_up, follow_up_concept = self._follow_up(question_type, gap, status, concept)

        strengths = []
        if satisfied:
            strengths.append(f"Mentioned key concepts: {', '.join(satisfied[:3])}.")
        elif relevance_ratio >= 0.7:
            strengths.append("Stayed on topic and used relevant technical terms.")

        return EvaluationDimensions(
            answer_status=status,
            relevance_score=relevance_score,
            understanding_score=understanding_score,
            correctness_score=correctness,
            completeness_score=completeness_score,
            reasoning_score=reasoning_score,
            satisfied_requirements=satisfied,
            partial_requirements=partial,
            missing_requirements=missing,
            technical_errors=technical_errors or [],
            misconceptions=technical_errors or [],
            contradictions=contradictions or [],
            recommended_topics=(missing[:3] or [concept]),
            follow_up_question=follow_up,
            follow_up_concept=follow_up_concept,
            confidence=round(0.6 + 0.3 * coverage, 2),
            strengths=strengths,
        )

    @staticmethod
    def _follow_up(
        question_type: str, gap: str, status: str, concept: str
    ) -> tuple[str, str]:
        if status not in {"partial", "on_topic"} or not gap:
            return "", ""
        if status == "on_topic":
            return "", ""  # strong answers get no follow-up
        starter = FOLLOWUP_STARTERS.get(normalize_type(question_type), FOLLOWUP_STARTERS["explanation"])
        return starter.format(topic=gap), concept

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    def generate_report(
        self,
        *,
        target_role: str,
        experience_level: str,
        analysis: CandidateAnalysis,
        skill_scores: list[dict],
        evaluations: list[dict],
    ) -> ReportSummary:
        if not evaluations:
            return ReportSummary(
                summary="The interview had no evaluated answers.",
                strengths=[],
                weaknesses=[],
                recommendations=["Answer all questions to receive a full report."],
            )
        best = max(skill_scores, key=lambda s: s["score"]) if skill_scores else None
        worst = min(skill_scores, key=lambda s: s["score"]) if skill_scores else None
        strengths = [f"Strongest area: {best['skill']} ({best['score']}/10)"] if best else []
        weaknesses = [f"Area to improve: {worst['skill']} ({worst['score']}/10)"] if worst else []
        recommendations = [f"Review materials on {w['skill']} and practice hands-on." for w in skill_scores if w["score"] < 7]
        if not recommendations:
            recommendations = ["Keep practicing with real projects to deepen your knowledge."]
        summary = (
            f"Completed the {target_role} ({experience_level}) interview. "
            f"Strong performance overall; focus on the highlighted weaker areas to grow."
        )
        return ReportSummary(
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
        )


# ---------------------------------------------------------------------------
# Heuristic helpers
# ---------------------------------------------------------------------------
def _is_knowledge_gap(text: str) -> bool:
    lower = " " + text.lower() + " "
    return any(p in lower for p in KNOWLEDGE_GAP_PATTERNS)


def _is_echo(question_text: str, answer_text: str, answer_words: list[str]) -> bool:
    """True when the answer essentially repeats the question back.

    Restating the question is not answering it, but an echo is built from the
    question's own topic vocabulary, so the relevance matcher would otherwise
    score it as on-topic. We flag it when the answer re-uses the question's
    content words in order (or the question verbatim) while adding almost no
    new content of its own.

    Directive verbs ("explain", "describe") are instructions, not content, so
    they are excluded from the question's content words; a trailing "please
    explain" in the answer must not defeat the check.
    """
    q_clean = re.sub(r"\s+", " ", re.sub(r"[^a-z'\s]", "", question_text.lower())).strip()
    a_clean = re.sub(r"\s+", " ", re.sub(r"[^a-z'\s]", "", answer_text.lower())).strip()
    q_content = [w for w in _content_words(question_text) if w not in DIRECTIVE_VERBS]
    a_content = [w for w in answer_words if w not in STOPWORDS]
    if not a_content:
        return False
    a_set = set(a_content)
    a_new = a_set - set(q_content) - DIRECTIVE_VERBS
    new_ratio = len(a_new) / len(a_set) if a_set else 0.0
    if new_ratio > 0.25:
        return False
    if q_clean and q_clean in a_clean:
        return True
    if len(q_content) < 2:
        return False
    pos = 0
    for w in a_content:
        if pos < len(q_content) and w == q_content[pos]:
            pos += 1
    return pos / len(q_content) >= 0.9


def _content_words(phrase: str) -> list[str]:
    return [w for w in re.findall(r"[a-z']+", phrase.lower()) if len(w) >= 3 and w not in STOPWORDS]


DIRECTIVE_VERBS = {
    "give", "provide", "describe", "mention", "write", "outline", "summarize",
    "tell", "explain", "compare", "design", "draw", "sketch", "show", "list",
}


def _requirements_state(
    requirements: list[str],
    answer_words: list[str],
    *,
    word_count: int = 0,
    topic_hits: set[str] | None = None,
    noise: set[str] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Classify each rubric requirement as satisfied / partial / missing.

    A requirement is satisfied when the majority of its content words appear in
    the answer (synonyms and common inflections count). Directive requirements
    ("Give a usage example", "Explain how X works") are additionally satisfied
    by a substantive, on-topic answer, so a concrete answer is not punished just
    because it avoids the exact wording.
    """
    present = _expand_terms(set(answer_words))
    satisfied: list[str] = []
    partial: list[str] = []
    missing: list[str] = []
    for req in requirements:
        raw_first = re.findall(r"[a-z']+", req.lower())
        directive = bool(raw_first) and raw_first[0] in DIRECTIVE_VERBS
        content = _content_words(req)
        if not content:
            missing.append(req)
            continue
        hit = sum(1 for w in content if not _word_group(w).isdisjoint(present))
        ratio = hit / len(content)
        if ratio >= 0.6:
            satisfied.append(req)
        elif (
            directive
            and word_count >= 12
            and topic_hits is not None
            and len(topic_hits) >= 1
            and (noise is None or len(noise) <= 2 * len(topic_hits) + 2)
        ):
            # A directive ("give an example") is addressed by any substantive
            # on-topic answer that isn't drowned in off-topic words, even if it
            # avoids the exact wording.
            satisfied.append(req)
        elif ratio >= 0.25:
            partial.append(req)
        else:
            missing.append(req)
    return satisfied, partial, missing


def _detect_misconceptions(misconceptions: list[str], answer_text: str) -> list[str]:
    """Flag a misconception when the answer states it.

    Strict matching: ALL content words of the misconception must appear in the
    answer. This is what makes "list and tuple are interchangeable" only fire
    when the candidate actually claims they are interchangeable — merely listing
    "list" and "tuple" as separate built-ins must not be flagged.

    Negation guard: if the answer contains any negation word we skip matching,
    because "a decorator is NOT a class" is a correct statement.
    """
    lower = answer_text.lower()
    if any(n in lower for n in ("not ", "n't", "never ", "doesn", "don't")):
        return []
    present = set(re.findall(r"[a-z']+", lower))
    found: list[str] = []
    for mc in misconceptions:
        content = [w for w in re.findall(r"[a-z']+", mc.lower()) if len(w) >= 3 and w not in STOPWORDS]
        if not content:
            continue
        # Single-token misconceptions ("a snake") match on that word alone;
        # multi-token ones require the statement's words to appear in the same
        # order. This stops a correct answer about default arguments ("Defaults
        # are evaluated once at definition time") from tripping "default
        # arguments are evaluated at call time" just because both share the
        # vocabulary "default/arguments/evaluated/time".
        if len(content) == 1:
            if content[0] in present:
                found.append(mc)
        else:
            pos = 0
            for w in re.findall(r"[a-z']+", lower):
                if pos < len(content) and w == content[pos]:
                    pos += 1
            if pos == len(content):
                found.append(mc)
    return found


def _word_group(word: str) -> frozenset[str]:
    """The synonym class a word belongs to (itself + inflection, by default)."""
    for group in SYNONYM_GROUPS:
        if word in group:
            return group
    base = word
    if base.endswith("ies") and len(base) > 4:
        base = base[:-3] + "y"
    elif base.endswith("es") and len(base) > 4:
        base = base[:-2]
    elif base.endswith("ing") and len(base) > 5:
        base = base[:-3]
    elif base.endswith("s") and not base.endswith("ss") and len(base) > 4:
        base = base[:-1]
    return frozenset({word, base})


def _expand_terms(words: set[str]) -> set[str]:
    """Expand a word set with synonym groups and common inflections."""
    expanded: set[str] = set()
    for w in words:
        expanded |= _word_group(w)
    return expanded


def _detect_contradictions(answer_text: str) -> list[str]:
    lower = answer_text.lower()
    found: list[str] = []
    for pair in CONTRADICTION_PAIRS:
        a, b = pair[0], pair[1]
        if all(x in lower for x in a) and all(x in lower for x in b):
            found.append(f"'{a[0]}' and '{b[0]}' are asserted together")
    return found


def _pick_gap(missing: list[str], partial: list[str], concept: str) -> str:
    for req in missing:
        if req.strip():
            return req.strip()
    for req in partial:
        if req.strip():
            return req.strip()
    return concept


def _rotate_type(current: str) -> str:
    cycle = ["explanation", "scenario", "coding", "tradeoff", "debugging", "definition"]
    idx = cycle.index(current) if current in cycle else 0
    return cycle[(idx + 1) % len(cycle)]
