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
    # Data-structure synonyms: a correct answer that says "hash map" instead of
    # "dict" or "sequence" instead of "list" must still match the rubric. The
    # mock evaluator deliberately avoids keyword-count credit, so these exist
    # to prevent *under*credit for synonymous terminology.
    frozenset({"list", "lists", "sequence", "sequences", "array", "arrays"}),
    frozenset({"dict", "dictionary", "dictionaries", "hash", "hashes",
               "hashing", "map", "maps", "mapping", "mappings", "associative"}),
    frozenset({"set", "sets", "hashset", "hashsets"}),
    frozenset({"lookup", "lookups", "membership", "member", "members"}),
    frozenset({"explain", "explains", "explained", "explaining", "explanation",
               "explanations", "describe", "describes", "described",
               "describing", "description", "descriptions"}),
)

# Thresholds
STUFFING_TECH_RATIO = 0.6
STUFFING_MAX_WORDS = 14
IRRELEVANT_RELEVANCE = 0.5
# The minimum answer length that can carry explanatory evidence. Shorter
# answers are treated as mention-only fragments ("Python decorator."). A
# short grammatical claim ("A decorator modifies a function.") is evidence.
MIN_EVIDENCE_WORDS = 4
MIN_EVIDENCE_PROSE_RATIO = 0.15
# A "real answer" to a coding question that contains no code must still show an
# implementation approach; anything shorter is treated as concept-only.
MIN_CODING_EXPLANATION_WORDS = 15
# Repetition: the answer may not add more than this share of novel content
# beyond the question + rubric before we stop calling it a copy.
MAX_REPETITION_NEW_RATIO = 0.4
REPETITION_CONTAINMENT = 0.9
REPETITION_SIMILARITY = 0.72
# The re-worded-repetition branch only fires when the answer is close in length
# to the text it is restating; padding a copy with filler still gets caught up
# to this multiple (the new_ratio + explanation-marker guards bound the risk).
REPETITION_MAX_LENGTH_MULTIPLE = 2.5

# Words/phrases a genuine answer uses when it moves past echoing the prompt.
# A light paraphrase of the question never needs them; a real answer almost
# always does. Their presence protects real answers that reuse the rubric's
# own vocabulary.
REPETITION_EXPLANATION_MARKERS = {
    "because", "example", "for example", "for instance", "such as", "means",
    "meaning", "which", "when", "if", "so that", "in practice", "in other words",
    "that is", "however", "instead", "but",
}

# A coding question needs code or an implementation approach. These words show
# the candidate actually planned the implementation rather than just defining
# the topic (e.g. "Data structures are things like lists..." has none of them).
CODING_IMPLICATION_MARKERS = {
    "write", "writes", "writing", "written", "wrote", "code", "codes", "coding",
    "function", "functions", "snippet", "algorithm", "algorithms", "implement",
    "implementation", "implementing", "build", "builds", "building", "built",
    "loop", "loops", "looping", "iterate", "iterates", "iterating", "iteration",
    "return", "returns", "returned", "program", "programs", "procedure",
    "step", "steps", "choose", "chooses", "choosing", "chosen", "pick",
    "picks", "picked", "use", "uses", "using", "used", "would", "approach",
    "approaches", "decision", "decisions", "then",
}


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
    #
    # Pipeline (each stage is a hard gate on the next):
    #   Candidate Answer
    #     -> 1. Answer Validation   (repetition / stuffing / gibberish /
    #                                knowledge gap / mention-only fragments)
    #     -> 2. Relevance Validation (off-topic answers stop here)
    #     -> 3. Understanding Assessment (evidence-based requirement coverage)
    #     -> 4. Technical Correctness   (misconceptions / contradictions)
    #     -> 5. Question-Type Requirement (e.g. coding answers must show code)
    #     -> 6. Status + Feedback + Score (ScoreEngine applies hard gates)
    #
    # Mention is never understanding: a concept only counts as demonstrated when
    # the answer provides evidence (an explanation, code, comparison, ...).
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
        answer_text = _normalize_complexity(answer_text)
        words = re.findall(r"[a-z']+", answer_text.lower())
        distinct = set(words)
        word_count = len(words)
        qtype = normalize_type(question_type)
        concept_name = concept or skill
        # Repetition is judged against the QUESTION and optional depth points
        # only. Expected concepts and core requirements describe what a correct
        # answer MUST contain, so reproducing their vocabulary is legitimate
        # answering, not an echo (keyword-list copies are caught separately by
        # the keyword-stuffing gate).
        given_texts = [question_text] + list(optional_depth_points)

        # Feature extraction (cheap; used by validation and knowledge stages).
        topic_vocab, relevant_vocab = _topic_vocabulary(
            skill, concept, question_text, expected_concepts, core_requirements
        )
        expanded_present = _expand_terms(distinct)
        topic_hits = expanded_present & topic_vocab
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

        # ================= STAGE 1: ANSWER VALIDATION =================
        # Raw tokens that belong to the topic: used by the keyword-stuffing
        # gate, which must count what was actually typed (a single "dictionary"
        # must not look like ten keywords via synonym expansion).
        raw_domain_hits = {
            w for w in distinct if not _word_group(w).isdisjoint(relevant_vocab)
        }
        non_answer = self._validate_answer(
            answer_text=answer_text,
            words=words,
            word_count=word_count,
            domain_terms=raw_domain_hits,
            topic_hits=topic_hits,
            relevance_ratio=relevance_ratio,
            given_texts=given_texts,
            core_requirements=core_requirements,
            concept=concept_name,
        )
        if non_answer is not None:
            return non_answer

        # ============ STAGE 2: RELEVANCE VALIDATION ============
        if not topic_hits and noise:
            return EvaluationDimensions(
                answer_status="irrelevant",
                relevance_score=round(10 * relevance_ratio, 1),
                understanding_score=round(10 * relevance_ratio, 1),
                correctness_score=2.0,
                completeness_score=0,
                reasoning_score=round(5 * relevance_ratio, 1),
                missing_requirements=list(core_requirements),
                recommended_topics=[concept_name],
                confidence=0.85,
                strengths=[],
            )

        # ========== STAGE 3: UNDERSTANDING ASSESSMENT ==========
        # Requirements are only satisfied by answers with evidence. Merely
        # printing a rubric keyword is never enough (keyword_count is not a
        # correctness signal).
        evidence = _has_evidence(words, distinct, word_count)
        satisfied, partial, missing = _requirements_state(
            core_requirements,
            words,
            evidence=evidence,
            topic_hits=topic_hits,
            noise=noise,
            word_count=word_count,
        )
        total = len(core_requirements) or 1
        coverage = (len(satisfied) + 0.5 * len(partial)) / total

        # ============ STAGE 4: TECHNICAL CORRECTNESS ============
        # Checked BEFORE the relevance gate: stating a known misconception or
        # contradicting yourself is a stronger signal than token relevance.
        misconceptions = _detect_misconceptions(common_misconceptions, answer_text)
        contradictions = _detect_contradictions(answer_text)

        mentioned, demonstrated = _concept_status(
            expected_concepts, words, satisfied=satisfied, evidence=evidence
        )

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
                mentioned=mentioned,
                demonstrated=demonstrated,
                concept=concept_name,
                skill=skill,
                question_type=qtype,
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
                mentioned=mentioned,
                demonstrated=demonstrated,
                concept=concept_name,
                skill=skill,
                question_type=qtype,
                technical_errors=misconceptions,
            )

        # ========== STAGE 5: QUESTION-TYPE REQUIREMENT ==========
        # A coding question is not answered by defining a dictionary; a
        # comparison question needs an actual comparison, etc.
        qtype_ok = _question_type_satisfied(
            qtype, answer_text, words, word_count, expected_concepts
        )
        if not qtype_ok:
            status = "incomplete"
            demonstrated = []
        elif coverage >= 0.8:
            status = "strong"
        elif evidence:
            status = "partial"
        else:
            status = "insufficient_evidence"
            demonstrated = []

        return self._dims_for(
            status=status,
            relevance_ratio=relevance_ratio,
            topic_density=topic_density,
            coverage=coverage,
            word_count=word_count,
            satisfied=satisfied,
            partial=partial,
            missing=missing,
            mentioned=mentioned,
            demonstrated=demonstrated,
            concept=concept_name,
            skill=skill,
            question_type=qtype,
        )

    # ------------------------------------------------------------------
    # Stage 1: Answer validation (non-answer gate)
    # ------------------------------------------------------------------
    def _validate_answer(
        self,
        *,
        answer_text: str,
        words: list[str],
        word_count: int,
        domain_terms: set[str],
        topic_hits: set[str],
        relevance_ratio: float,
        given_texts: list[str],
        core_requirements: list[str],
        concept: str,
    ) -> EvaluationDimensions | None:
        """Return gated dimensions when the answer is a non-answer, else None."""
        missing = list(core_requirements)

        if _is_knowledge_gap(answer_text):
            return EvaluationDimensions(
                answer_status="knowledge_gap",
                relevance_score=0.5,
                understanding_score=0,
                correctness_score=0,
                completeness_score=0,
                reasoning_score=0,
                missing_requirements=missing,
                recommended_topics=[concept],
                confidence=0.9,
                strengths=["Was honest about not knowing."],
            )

        if not _content_words(answer_text):
            return EvaluationDimensions(
                answer_status="nonsensical",
                relevance_score=0,
                understanding_score=0,
                correctness_score=0,
                completeness_score=0,
                reasoning_score=0,
                missing_requirements=missing,
                recommended_topics=[concept],
                confidence=0.9,
                strengths=[],
            )

        if _is_repetition(given_texts, answer_text, words):
            return EvaluationDimensions(
                answer_status="question_repetition",
                relevance_score=2.0,
                understanding_score=0,
                correctness_score=0,
                completeness_score=0,
                reasoning_score=0,
                missing_requirements=missing,
                recommended_topics=[concept],
                confidence=0.95,
                strengths=[],
            )

        if _is_keyword_stuffing(domain_terms, words, word_count):
            return EvaluationDimensions(
                answer_status="keyword_stuffing",
                relevance_score=3.0,
                understanding_score=0.5,
                correctness_score=0.5,
                completeness_score=0,
                reasoning_score=0,
                missing_requirements=missing,
                recommended_topics=[concept],
                confidence=0.9,
                strengths=[],
            )

        if topic_hits and word_count < MIN_EVIDENCE_WORDS:
            # A fragment like "Python decorator." or "dictionary." mentions the
            # concept but demonstrates nothing.
            return EvaluationDimensions(
                answer_status="insufficient_evidence",
                relevance_score=round(10 * relevance_ratio, 1),
                understanding_score=0,
                correctness_score=0,
                completeness_score=0,
                reasoning_score=0,
                missing_requirements=missing,
                recommended_topics=[concept],
                confidence=0.85,
                strengths=[],
            )

        return None

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
        mentioned: list[str],
        demonstrated: list[str],
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

        # Strengths must reflect DEMONSTRATED understanding. A concept that was
        # merely mentioned is never a strength.
        strengths = []
        if satisfied:
            strengths.append(f"Demonstrated: {', '.join(satisfied[:3])}.")
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
            mentioned_concepts=mentioned,
            demonstrated_concepts=demonstrated,
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
        if status not in {"partial", "incomplete"} or not gap:
            return "", ""
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


def _normalized(text: str) -> str:
    """Lowercase, punctuation-free, whitespace-collapsed text for comparison."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z'\s]", "", text.lower())).strip()


def _is_repetition(
    given_texts: list[str], answer_text: str, answer_words: list[str]
) -> bool:
    """True when the answer is essentially a copy of what the candidate was given.

    Detects verbatim copies, near-duplicates (trivial edits), and re-worded
    repetition, against the question AND the rubric (expected concepts,
    requirements, optional depth points). Restating the prompt is not answering
    it, but an echo is built from the prompt's own vocabulary, so the relevance
    matcher would otherwise reward it.

    A guard requires the answer to add almost no new content of its own
    (``new_ratio``), so a genuine explanation that reuses the rubric's standard
    vocabulary is not falsely flagged.
    """
    a_clean = _normalized(answer_text)
    if not a_clean:
        return False
    # A response that adds reasoning, examples or code is an answer, even if it
    # reuses the prompt's vocabulary. Only copy-without-content is repetition.
    if _looks_like_code(answer_text):
        return False
    if any(marker in answer_text.lower() for marker in REPETITION_EXPLANATION_MARKERS):
        return False
    given_content = set()
    for text in given_texts:
        given_content.update(_content_words(text))
    a_content = [w for w in answer_words if w not in STOPWORDS]
    if not a_content:
        return False
    a_set = set(a_content)
    # Synonyms of given words (e.g. "explanation" for "explain") are not new
    # content, so a light rephrasing of the prompt is still detectable.
    given_expanded = _expand_terms(given_content)
    a_new = {
        w for w in a_set if _word_group(w).isdisjoint(given_expanded)
    } - DIRECTIVE_VERBS
    new_ratio = len(a_new) / len(a_set) if a_set else 0.0
    if new_ratio > MAX_REPETITION_NEW_RATIO:
        return False

    from difflib import SequenceMatcher

    for text in given_texts:
        t_clean = _normalized(text)
        if not t_clean:
            continue
        # A too-short given text (e.g. a bare expected concept like "Python")
        # would match any answer that merely mentions it. Repetition is judged
        # against phrases with real substance.
        if len(_content_words(text)) < 3:
            continue
        # Verbatim / near-verbatim copy of a given string.
        if t_clean in a_clean or a_clean in t_clean:
            return True
        # Trivial edits (typos, small reorderings, added filler).
        if SequenceMatcher(None, t_clean, a_clean).ratio() >= REPETITION_SIMILARITY:
            return True
        # Re-worded: the given text's content words recur in order, and the
        # answer is not much longer than the text it is restating.
        t_content = [w for w in _content_words(text) if w not in DIRECTIVE_VERBS]
        if len(t_content) < 2:
            continue
        if len(a_content) > len(t_content) * REPETITION_MAX_LENGTH_MULTIPLE:
            continue
        pos = 0
        for w in a_content:
            if pos < len(t_content) and w == t_content[pos]:
                pos += 1
        if pos / len(t_content) >= REPETITION_CONTAINMENT:
            return True
    return False


def _is_keyword_stuffing(
    domain_terms: set[str], words: list[str], word_count: int
) -> bool:
    """A dense burst of domain words with no connecting language is not an answer.

    ``domain_terms`` = the answer's words that are glossary OR question
    vocabulary (synonym-expanded). With zero glue words the candidate is
    listing terms, not explaining them.
    """
    glue = {w for w in words if w in STOPWORDS}
    if len(glue) > 0:
        return False
    if len(domain_terms) < 4:
        return False
    return (
        word_count <= STUFFING_MAX_WORDS
        and len(domain_terms) / max(word_count, 1) >= STUFFING_TECH_RATIO
    )


def _has_evidence(words: list[str], distinct: set[str], word_count: int) -> bool:
    """Does the answer demonstrate understanding, or just mention keywords?

    Evidence means real prose: enough words AND connecting language. A keyword
    list ("decorator wrapper functools") has no glue; a one-word answer has no
    structure. Both can mention the topic but do not explain it.
    """
    if word_count < MIN_EVIDENCE_WORDS:
        return False
    glue = sum(1 for w in words if w in STOPWORDS)
    return glue / word_count >= MIN_EVIDENCE_PROSE_RATIO


def _content_words(phrase: str) -> list[str]:
    return [w for w in re.findall(r"[a-z']+", phrase.lower()) if len(w) >= 3 and w not in STOPWORDS]


DIRECTIVE_VERBS = {
    "give", "provide", "describe", "mention", "write", "outline", "summarize",
    "tell", "explain", "compare", "design", "draw", "sketch", "show", "list",
}


def _normalize_complexity(text: str) -> str:
    """Turn big-O notation into words so the rubric matcher can see it.

    "O(1)" is the answer to a "time complexity" requirement but the tokenizer
    only sees "o" and "1". Spell it out so requirement matching and vocabulary
    work on the semantics, not the typography.
    """
    text = re.sub(r"\bO\s*\(\s*1\s*\)", "constant time", text, flags=re.IGNORECASE)
    text = re.sub(r"\bO\s*\(\s*log\s*\w*\s*\)", "logarithmic time", text, flags=re.IGNORECASE)
    text = re.sub(r"\bO\s*\(\s*n\s*\)", "linear time", text, flags=re.IGNORECASE)
    return text


def _topic_vocabulary(
    skill: str,
    concept: str | None,
    question_text: str,
    expected_concepts: list[str],
    core_requirements: list[str],
) -> tuple[set[str], set[str]]:
    """Question-specific vocabulary: topic terms and the broader relevant terms.

    An answer is on-topic when it engages THIS question's concept words, not
    just any technical vocabulary ("indexes/transactions" don't answer a
    decorator question). Generic tech words still contribute, but with half the
    weight. Both sides are synonym/inflection-expanded, so "begins" counts for
    a rubric that says "begin".
    """
    topic_words: set[str] = set()
    for phrase in [skill, concept or "", question_text] + expected_concepts + core_requirements:
        topic_words.update(_content_words(phrase))
    topic_vocab = _expand_terms(topic_words)
    relevant_vocab = _expand_terms(set(TECH_TERMS)) | topic_vocab
    return topic_vocab, relevant_vocab


def _requirements_state(
    requirements: list[str],
    answer_words: list[str],
    *,
    evidence: bool,
    word_count: int = 0,
    topic_hits: set[str] | None = None,
    noise: set[str] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Classify each rubric requirement as satisfied / partial / missing.

    A requirement is only satisfied when the answer has EVIDENCE of
    understanding (real prose, not a keyword list) AND the majority of its
    content words appear (synonyms and common inflections count). Directive
    requirements ("Give a usage example") are additionally satisfied by a
    substantive, on-topic answer. Without evidence, everything is missing:
    mentioning the rubric's words is not demonstrating the concept.
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
        if not evidence:
            missing.append(req)
        elif ratio >= 0.6:
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


def _concept_status(
    expected_concepts: list[str],
    answer_words: list[str],
    *,
    satisfied: list[str],
    evidence: bool,
) -> tuple[list[str], list[str]]:
    """Split expected concepts into ``(mentioned, demonstrated)``.

    ``mentioned`` = the concept's words appear somewhere in the answer.
    ``demonstrated`` = a subset of ``mentioned``: the answer shows real
    evidence AND the concept's words are backed by a satisfied rubric
    requirement. Mention is never understanding on its own.
    """
    present = _expand_terms(set(answer_words))
    mentioned: list[str] = []
    for concept in expected_concepts:
        cw = _content_words(concept)
        if cw and any(not _word_group(w).isdisjoint(present) for w in cw):
            mentioned.append(concept)

    demonstrated: list[str] = []
    if not evidence or not satisfied:
        return mentioned, demonstrated
    sat_words: set[str] = set()
    for req in satisfied:
        sat_words.update(_content_words(req))
    sat_expanded = _expand_terms(sat_words)
    for concept in mentioned:
        cw = _content_words(concept)
        if any(not _word_group(w).isdisjoint(sat_expanded) for w in cw):
            demonstrated.append(concept)
    return mentioned, demonstrated


# Vocabulary that shows the candidate actually did the reasoning the question
# type asked for (vs. merely mentioning the topic).
TYPE_REQUIREMENT_MARKERS: dict[str, set[str]] = {
    "comparison": {
        "vs", "versus", "compared", "compare", "comparing", "unlike", "whereas",
        "while", "difference", "differences", "different", "differ", "instead",
        "however", "but", "trade-off", "tradeoff", "similar", "similarly",
        "both",
    },
    "tradeoff": {
        "trade-off", "tradeoff", "trade", "cost", "costs", "however",
        "instead", "vs", "versus", "benefit", "benefits", "pros", "cons",
    },
    "debugging": {
        "check", "checked", "checking", "look", "looks", "looked", "run",
        "runs", "trace", "traces", "cause", "causes", "error", "errors",
        "diagnose", "diagnosing", "reproduce", "fix", "fixed", "fixing",
        "hypothesis", "isolate", "log", "logs", "step", "steps",
    },
    "scenario": {
        "would", "choose", "choosing", "chosen", "because", "trade-off",
        "tradeoff", "prefer", "preferred", "preferring", "assuming", "decide",
        "deciding", "depend", "depends", "depending",
    },
    "system_design": {
        "scale", "scaling", "scalable", "load", "traffic", "latency",
        "throughput", "cache", "caching", "availability", "consistency",
        "shard", "sharding", "shards", "partition", "partitioning", "replica",
        "replicas", "queue", "queues", "distribute", "distributing",
        "distribution", "architecture", "architect",
    },
}


def _looks_like_code(text: str) -> bool:
    """Heuristic: does the answer contain actual code or code-shaped syntax?"""
    t = text.lower()
    patterns = (
        r"\bdef\s+\w+", r"\bclass\s+\w+", r"\bimport\s+\w+", r"\bfrom\s+\w+\s+import",
        r"\breturn\b", r"\blambda\b", r"\byield\b", r"\bfor\s+\w+\s+in\b", r"\bwhile\b",
        r"\belse\s*:", r"\belif\b", r"->", r"==", r"!=", r"\+=", r"\{", r"\}",
        r"\w+\s*=\s*\w+", r"\w+\s*\([^)]*\)\s*[:=]", r";",
    )
    return any(re.search(p, t) for p in patterns)


def _question_type_satisfied(
    question_type: str,
    answer_text: str,
    words: list[str],
    word_count: int,
    expected_concepts: list[str],
) -> bool:
    """Did the answer satisfy the question type's structural requirement?

    Explanation/definition/behavioral answers only need prose evidence. The
    other types demand the specific reasoning (code or an implementation
    approach for coding, an actual comparison, a diagnostic approach, ...).
    An answer that merely defines the topic does NOT satisfy a coding or
    comparison question.
    """
    present = _expand_terms(set(words))
    if question_type in {"explanation", "definition", "behavioral", "architecture"}:
        return _has_evidence(words, present, word_count)

    if question_type == "coding":
        if _looks_like_code(answer_text):
            return True
        # No code, but a substantive implementation approach is acceptable.
        if word_count < MIN_CODING_EXPLANATION_WORDS or not _has_evidence(words, present, word_count):
            return False
        return any(w in CODING_IMPLICATION_MARKERS for w in words)

    if question_type == "comparison":
        if not _has_evidence(words, present, word_count):
            return False
        lower = answer_text.lower()
        contrast = TYPE_REQUIREMENT_MARKERS["comparison"]
        if any(w in contrast for w in words) or any(
            phrase in lower
            for phrase in ("on the other hand", "in contrast", "by contrast",
                           "versus", "vs.")
        ):
            return True
        # No explicit contrast word, but the answer may still compare: it
        # engages at least two of the entities the question asks about.
        covered = sum(
            1
            for c in expected_concepts
            if any(not _word_group(w).isdisjoint(present) for w in _content_words(c))
        )
        return covered >= 2 and word_count >= 12

    if question_type in {"scenario", "tradeoff"}:
        if not _has_evidence(words, present, word_count):
            return False
        markers = TYPE_REQUIREMENT_MARKERS.get(question_type, set())
        if any(w in markers for w in words):
            return True
        # No explicit scenario word, but the answer may still reason about the
        # situation: it engages at least two of the expected concepts with
        # enough prose to be a real answer (e.g. "locks and deadlocks still
        # need care" for a concurrency scenario).
        covered = sum(
            1
            for c in expected_concepts
            if any(not _word_group(w).isdisjoint(present) for w in _content_words(c))
        )
        return covered >= 2 and word_count >= 12

    markers = TYPE_REQUIREMENT_MARKERS.get(question_type, set())
    if not markers:
        return _has_evidence(words, present, word_count)
    if not _has_evidence(words, present, word_count):
        return False
    return any(w in markers for w in words)


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
