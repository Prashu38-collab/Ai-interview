"""Curated, extensible concept bank.

This is the single source of "what can be asked". It is pure data: skills map
to concepts, and each concept knows the question types it supports, the key
points a strong answer should touch, common misconceptions, and seed questions.

The mock provider generates questions + rubrics from these specs, the planner
selects concepts to target, the validator checks that LLM output fits a known
concept (and falls back to a seed), and the mock evaluator uses ``key_points``
as the rubric and ``misconceptions`` to spot wrong definitions.

To support a new technology, add a skill entry here — no logic changes needed.
"""

from pydantic import BaseModel, Field

# The question types the platform understands. Legacy "conceptual" is accepted
# everywhere but normalised to "explanation".
QUESTION_TYPES: tuple[str, ...] = (
    "definition",
    "explanation",
    "comparison",
    "scenario",
    "debugging",
    "coding",
    "system_design",
    "behavioral",
    "architecture",
    "tradeoff",
)

QUESTION_TYPE_ALIASES: dict[str, str] = {
    "conceptual": "explanation",
}

QUESTION_TYPE_LABELS: dict[str, str] = {
    "definition": "Definition",
    "explanation": "Explanation",
    "comparison": "Comparison",
    "scenario": "Scenario",
    "debugging": "Debugging",
    "coding": "Coding",
    "system_design": "System design",
    "behavioral": "Behavioral",
    "architecture": "Architecture",
    "tradeoff": "Trade-off",
}


class ConceptSpec(BaseModel):
    """One concept inside a skill."""

    name: str
    # Typical difficulty for the concept. The planner can deviate from this
    # based on demonstrated performance.
    difficulty: str = "medium"
    # Question types this concept can be asked as.
    question_types: list[str] = Field(
        default_factory=lambda: ["definition", "explanation"]
    )
    # Rubric seeds: the things a strong answer demonstrates.
    key_points: list[str] = Field(default_factory=list)
    # Wrong statements candidates often make; the evaluator watches for these.
    misconceptions: list[str] = Field(default_factory=list)
    # question_type -> seed question template. "{concept}" and "{skill}" are
    # substituted at generation time. Falls back to QUESTION_TYPE_TEMPLATES.
    seeds: dict[str, str] = Field(default_factory=dict)


# Generic phrasing fallbacks when a concept has no type-specific seed.
QUESTION_TYPE_TEMPLATES: dict[str, str] = {
    "definition": "What is {concept}?",
    "explanation": "Explain {concept} and why it matters when working with {skill}.",
    "comparison": "Compare {concept} with its closest alternative in {skill}. What are the trade-offs?",
    "scenario": "Describe a real-world situation in {skill} where {concept} is the right tool. How would you apply it?",
    "debugging": "Something is going wrong with {concept} in your {skill} system. How do you investigate and fix it?",
    "coding": "Write a short snippet using {concept} in {skill}. What are the key design decisions?",
    "system_design": "Design a component of a {skill} system where {concept} is central. Discuss bottlenecks and trade-offs.",
    "behavioral": "Tell me about a time you used {concept} at work or school and what you learned.",
    "architecture": "How would you structure a {skill} system around {concept}? What are the main architectural concerns?",
    "tradeoff": "What trade-offs does {concept} introduce in a production {skill} system?",
}

# Follow-up starters: how an interviewer deepens a weak answer.
FOLLOWUP_STARTERS: dict[str, str] = {
    "definition": "Can you go a level deeper: {topic}?",
    "explanation": "That is the basic idea. Can you explain the mechanics: {topic}?",
    "comparison": "Where do the two approaches diverge: {topic}?",
    "scenario": "Walk me through what happens step by step: {topic}?",
    "debugging": "What would you check first and why: {topic}?",
    "coding": "Can you sketch how that would look in code: {topic}?",
    "system_design": "How would that hold up at scale: {topic}?",
    "behavioral": "What would you do differently next time: {topic}?",
    "architecture": "How does that decision affect the rest of the system: {topic}?",
    "tradeoff": "What breaks if you optimize for {topic}?",
}

# ---------------------------------------------------------------------------
# The bank. Add a skill here to support a new technology.
# ---------------------------------------------------------------------------
CONCEPT_BANK: dict[str, list[ConceptSpec]] = {
    "Python": [
        ConceptSpec(
            name="variables and data types",
            difficulty="easy",
            question_types=["definition", "explanation", "coding"],
            key_points=[
                "Python is dynamically typed",
                "mutable vs immutable types",
                "common built-ins (int, float, str, list, dict, tuple, set)",
            ],
            misconceptions=["Python is a compiled language", "list and tuple are interchangeable"],
        ),
        ConceptSpec(
            name="data structures",
            difficulty="easy",
            question_types=["comparison", "scenario", "coding"],
            key_points=[
                "list vs tuple vs set vs dict",
                "time complexity of common operations",
                "choosing the right structure for the problem",
            ],
            misconceptions=["dict keys can be any object", "sets preserve insertion order"],
            seeds={
                "comparison": "Compare lists, tuples and sets in Python. When would you pick each one?",
                "scenario": "You need to deduplicate a large list of names and look them up fast. Which Python data structures would you use and why?",
            },
        ),
        ConceptSpec(
            name="functions and scoping",
            difficulty="easy",
            question_types=["explanation", "coding", "scenario"],
            key_points=[
                "function definition and call",
                "arguments, defaults, *args/**kwargs",
                "scope and the LEGB rule",
            ],
            misconceptions=["default arguments are evaluated at call time"],
        ),
        ConceptSpec(
            name="decorators",
            difficulty="medium",
            question_types=["definition", "explanation", "coding", "scenario"],
            key_points=[
                "decorators are functions that take a callable and return a wrapped callable",
                "they modify or extend behaviour without changing the original source",
                "common uses: logging, timing, caching, auth",
                "functools.wraps preserves metadata",
            ],
            misconceptions=[
                "a decorator is a class",
                "a decorator permanently modifies the original function",
                "a decorator only works on functions, not methods",
            ],
            seeds={
                "definition": "What is a Python decorator and why would you use one?",
                "explanation": "Explain how a Python decorator wraps a function and give a practical use case.",
                "coding": "Write a decorator that logs the arguments and execution time of any function.",
            },
        ),
        ConceptSpec(
            name="generators and iterators",
            difficulty="medium",
            question_types=["explanation", "comparison", "coding"],
            key_points=[
                "iterators implement __iter__ and __next__",
                "generators are lazy iterators written with yield",
                "memory benefits for large or infinite sequences",
            ],
            misconceptions=["a generator holds all its values in memory"],
        ),
        ConceptSpec(
            name="exceptions and error handling",
            difficulty="easy",
            question_types=["explanation", "scenario", "debugging", "coding"],
            key_points=[
                "try/except/else/finally",
                "catching specific exceptions, not bare except",
                "raising meaningful exceptions",
            ],
            misconceptions=["except Exception swallows keyboard interrupts safely"],
        ),
        ConceptSpec(
            name="object oriented programming",
            difficulty="medium",
            question_types=["explanation", "comparison", "coding"],
            key_points=[
                "classes, objects, inheritance, polymorphism, encapsulation",
                "dunder methods",
                "composition over inheritance",
            ],
            misconceptions=["private attributes are enforced by Python"],
        ),
        ConceptSpec(
            name="async programming",
            difficulty="hard",
            question_types=["explanation", "comparison", "debugging", "system_design"],
            key_points=[
                "event loop and coroutines",
                "async/await semantics",
                "asyncio concurrency vs threads",
                "blocking calls inside async code",
            ],
            misconceptions=["async code runs in parallel threads", "asyncio makes CPU-bound code faster"],
            seeds={
                "explanation": "Explain how asyncio's event loop schedules coroutines.",
                "debugging": "A FastAPI endpoint using asyncio suddenly blocks under load. How do you investigate?",
            },
        ),
        ConceptSpec(
            name="testing",
            difficulty="easy",
            question_types=["explanation", "scenario", "coding"],
            key_points=[
                "unit vs integration tests",
                "pytest fixtures and assertions",
                "test isolation and determinism",
            ],
            misconceptions=["tests should share state for speed"],
        ),
    ],
    "PostgreSQL": [
        ConceptSpec(
            name="joins",
            difficulty="medium",
            question_types=["explanation", "scenario", "coding"],
            key_points=[
                "inner vs left/right/full outer",
                "join conditions and row multiplication",
                "indexing implications of joins",
            ],
            misconceptions=["a LEFT JOIN always returns fewer rows than an INNER JOIN"],
        ),
        ConceptSpec(
            name="indexes",
            difficulty="medium",
            question_types=["explanation", "scenario", "debugging", "tradeoff", "system_design"],
            key_points=[
                "indexes speed up lookups by scanning less data",
                "B-tree structure and how rows are located",
                "write cost and storage trade-offs",
                "partial and covering indexes",
            ],
            misconceptions=["indexes only make things faster", "every column needs an index"],
            seeds={
                "explanation": "How does a database index help PostgreSQL find the requested rows?",
                "tradeoff": "What trade-offs do indexes introduce in a high-write workload?",
                "debugging": "A slow query has an index but is still slow. How would you investigate?",
            },
        ),
        ConceptSpec(
            name="transactions and ACID",
            difficulty="medium",
            question_types=["explanation", "scenario", "debugging", "system_design"],
            key_points=[
                "ACID properties",
                "begin/commit/rollback",
                "MVCC and isolation levels",
                "locks and deadlocks",
            ],
            misconceptions=["transactions prevent all concurrency problems"],
            seeds={
                "scenario": "Two users update the same account balance simultaneously. How do transactions help, and what still needs care?",
            },
        ),
        ConceptSpec(
            name="normalization",
            difficulty="medium",
            question_types=["definition", "explanation", "scenario", "tradeoff"],
            key_points=[
                "eliminate redundancy",
                "first through third normal form",
                "denormalization trade-offs for reads",
            ],
            misconceptions=["normalization means splitting every table into tiny pieces"],
        ),
        ConceptSpec(
            name="query optimization",
            difficulty="hard",
            question_types=["scenario", "debugging", "tradeoff"],
            key_points=[
                "EXPLAIN ANALYZE and reading plans",
                "seq scan vs index scan",
                "missing statistics and outdated plans",
                "N+1 queries",
            ],
            misconceptions=["EXPLAIN without ANALYZE measures real execution cost"],
        ),
        ConceptSpec(
            name="locking and concurrency",
            difficulty="hard",
            question_types=["explanation", "scenario", "debugging", "system_design"],
            key_points=[
                "row vs table locks",
                "MVCC readers vs writers",
                "deadlock detection",
                "lock contention patterns",
            ],
            misconceptions=["SELECT blocks on writes"],
        ),
    ],
    "FastAPI": [
        ConceptSpec(
            name="dependency injection",
            difficulty="medium",
            question_types=["explanation", "scenario", "coding"],
            key_points=[
                "Depends() and reusable dependencies",
                "request-scoped state (db sessions, auth)",
                "testing with dependency overrides",
            ],
            misconceptions=["dependencies are global singletons"],
        ),
        ConceptSpec(
            name="pydantic validation",
            difficulty="easy",
            question_types=["explanation", "coding", "debugging"],
            key_points=[
                "request/response models",
                "automatic 422 responses",
                "custom validators",
            ],
            misconceptions=["validation only happens for the database"],
        ),
        ConceptSpec(
            name="authentication",
            difficulty="medium",
            question_types=["scenario", "architecture", "coding"],
            key_points=[
                "OAuth2 password flow and JWT",
                "protecting routes with dependencies",
                "token expiry and refresh",
            ],
            misconceptions=["JWT tokens are encrypted"],
        ),
        ConceptSpec(
            name="async endpoints",
            difficulty="medium",
            question_types=["explanation", "scenario", "debugging", "architecture"],
            key_points=[
                "def vs async def",
                "running sync work in a threadpool",
                "never blocking the event loop",
            ],
            misconceptions=["async def is always faster"],
        ),
        ConceptSpec(
            name="middleware and lifespan",
            difficulty="medium",
            question_types=["explanation", "architecture", "scenario"],
            key_points=[
                "middleware ordering",
                "CORS and logging middleware",
                "lifespan for startup/shutdown",
            ],
            misconceptions=["middleware runs once per server start"],
        ),
    ],
    "Docker": [
        ConceptSpec(
            name="images and containers",
            difficulty="easy",
            question_types=["definition", "explanation", "coding"],
            key_points=[
                "image is a read-only template; container is a running instance",
                "layers and Dockerfile instructions",
                "images are cached and reused",
            ],
            misconceptions=["a container is a lightweight virtual machine"],
        ),
        ConceptSpec(
            name="dockerfiles",
            difficulty="easy",
            question_types=["coding", "explanation", "debugging"],
            key_points=[
                "multi-stage builds",
                "layer caching and build order",
                "minimising image size",
            ],
            misconceptions=["every RUN creates a permanent layer you should keep"],
        ),
        ConceptSpec(
            name="networking and volumes",
            difficulty="medium",
            question_types=["explanation", "scenario", "architecture"],
            key_points=[
                "bridge networks and container DNS",
                "named volumes vs bind mounts",
                "persistence across container restarts",
            ],
            misconceptions=["data in a container is lost only on image rebuild"],
        ),
        ConceptSpec(
            name="compose and orchestration",
            difficulty="medium",
            question_types=["explanation", "scenario", "architecture"],
            key_points=[
                "services, networks, volumes in compose",
                "depends_on and health checks",
                "env and secrets handling",
            ],
            misconceptions=["compose provides container restart across hosts"],
        ),
    ],
    "AWS": [
        ConceptSpec(
            name="s3",
            difficulty="easy",
            question_types=["definition", "scenario", "architecture"],
            key_points=[
                "object storage, buckets, keys",
                "durability and availability",
                "lifecycle and versioning",
            ],
            misconceptions=["S3 is a file system you can mount everywhere"],
        ),
        ConceptSpec(
            name="lambda",
            difficulty="medium",
            question_types=["explanation", "scenario", "architecture", "tradeoff"],
            key_points=[
                "event-driven, stateless function execution",
                "cold starts",
                "timeouts, concurrency and limits",
            ],
            misconceptions=["Lambda has no cold start for predictable workloads"],
        ),
        ConceptSpec(
            name="ec2",
            difficulty="easy",
            question_types=["definition", "scenario"],
            key_points=[
                "virtual machines with persisted EBS volumes",
                "security groups and key pairs",
                "auto scaling groups",
            ],
            misconceptions=["security groups are stateful firewalls only"],
        ),
        ConceptSpec(
            name="iam",
            difficulty="medium",
            question_types=["explanation", "scenario", "architecture"],
            key_points=[
                "users, roles, policies",
                "least privilege",
                "temporary credentials",
            ],
            misconceptions=["IAM policies are only for people"],
        ),
        ConceptSpec(
            name="rds",
            difficulty="medium",
            question_types=["explanation", "scenario", "architecture"],
            key_points=[
                "managed relational databases",
                "multi-AZ and read replicas",
                "backups and snapshots",
            ],
            misconceptions=["RDS read replicas accept writes"],
        ),
    ],
    "REST APIs": [
        ConceptSpec(
            name="http methods",
            difficulty="easy",
            question_types=["definition", "explanation", "coding"],
            key_points=[
                "GET, POST, PUT, PATCH, DELETE semantics",
                "idempotency of PUT vs POST",
                "status code usage",
            ],
            misconceptions=["PUT and PATCH are interchangeable"],
            seeds={
                "explanation": "Explain REST APIs and the difference between PUT and PATCH.",
            },
        ),
        ConceptSpec(
            name="status codes",
            difficulty="easy",
            question_types=["definition", "explanation", "debugging"],
            key_points=[
                "2xx success, 3xx redirect, 4xx client, 5xx server",
                "choosing precise codes",
                "error response bodies",
            ],
            misconceptions=["400 is the correct answer for any client problem"],
        ),
        ConceptSpec(
            name="restful design",
            difficulty="medium",
            question_types=["explanation", "scenario", "architecture"],
            key_points=[
                "resources and collections",
                "statelessness",
                "versioning and pagination",
            ],
            misconceptions=["REST requires JSON only"],
        ),
        ConceptSpec(
            name="authentication and authorization",
            difficulty="medium",
            question_types=["definition", "explanation", "scenario"],
            key_points=[
                "authentication establishes identity",
                "authorization grants access",
                "JWT, tokens, scopes",
            ],
            misconceptions=[
                "authentication determines what resources the user can access",
                "authorization verifies who the user is",
            ],
            seeds={
                "definition": "What is the difference between authentication and authorization?",
                "scenario": "A user can log in but cannot read the admin dashboard. Which of the two concepts failed and why?",
            },
        ),
        ConceptSpec(
            name="pagination and filtering",
            difficulty="medium",
            question_types=["explanation", "scenario", "architecture"],
            key_points=[
                "offset vs cursor pagination",
                "filtering and sorting on the server",
                "consistent ordering",
            ],
            misconceptions=["pagination guarantees stable results without an order clause"],
        ),
    ],
    "React": [
        ConceptSpec(
            name="components and props",
            difficulty="easy",
            question_types=["explanation", "coding"],
            key_points=[
                "function components",
                "props as inputs",
                "composition",
            ],
            misconceptions=["props are mutable within the child"],
        ),
        ConceptSpec(
            name="state and hooks",
            difficulty="medium",
            question_types=["explanation", "scenario", "coding", "debugging"],
            key_points=[
                "useState, useEffect, useMemo, useCallback",
                "closure and dependency arrays",
                "unidirectional data flow",
            ],
            misconceptions=["useEffect runs after every render unconditionally"],
        ),
        ConceptSpec(
            name="reconciliation and keys",
            difficulty="medium",
            question_types=["explanation", "debugging", "tradeoff"],
            key_points=[
                "virtual DOM diffing",
                "stable keys for lists",
                "avoiding unnecessary re-renders",
            ],
            misconceptions=["index keys are always safe"],
        ),
        ConceptSpec(
            name="routing and data fetching",
            difficulty="medium",
            question_types=["scenario", "architecture", "coding"],
            key_points=[
                "client-side routing",
                "loading and error states",
                "cache and stale data",
            ],
            misconceptions=["every route change should refetch everything"],
        ),
    ],
    "System Design": [
        ConceptSpec(
            name="load balancing",
            difficulty="medium",
            question_types=["explanation", "architecture", "tradeoff"],
            key_points=[
                "distributing traffic across servers",
                "health checks and sessions",
                "L4 vs L7 balancing",
            ],
            misconceptions=["a load balancer makes a system strongly consistent"],
        ),
        ConceptSpec(
            name="caching",
            difficulty="medium",
            question_types=["explanation", "architecture", "scenario", "tradeoff"],
            key_points=[
                "cache-aside vs write-through",
                "TTL and invalidation",
                "cache stampede",
            ],
            misconceptions=["caching makes data more up to date"],
        ),
        ConceptSpec(
            name="message queues",
            difficulty="medium",
            question_types=["explanation", "architecture", "scenario"],
            key_points=[
                "decoupling producers and consumers",
                "at-least-once vs exactly-once",
                "retries and dead-letter queues",
            ],
            misconceptions=["queues guarantee in-order delivery"],
        ),
        ConceptSpec(
            name="scalability",
            difficulty="hard",
            question_types=["explanation", "architecture", "tradeoff"],
            key_points=[
                "vertical vs horizontal scaling",
                "stateless services",
                "sharding and replication",
            ],
            misconceptions=["horizontal scaling always solves a database bottleneck"],
        ),
        ConceptSpec(
            name="consistency models",
            difficulty="hard",
            question_types=["explanation", "tradeoff", "architecture"],
            key_points=[
                "strong vs eventual consistency",
                "CAP theorem in practice",
                "choosing based on requirements",
            ],
            misconceptions=["you can have all of CAP"],
        ),
    ],
    "Behavioral": [
        ConceptSpec(
            name="teamwork and collaboration",
            difficulty="easy",
            question_types=["behavioral", "scenario"],
            key_points=[
                "specific situation with a concrete example",
                "your role and contribution",
                "outcome and what you learned",
            ],
            misconceptions=[],
            seeds={
                "behavioral": "Describe a time you disagreed with a teammate on a technical decision. How did you resolve it?",
                "scenario": "A teammate is blocking your feature. How do you handle it?",
            },
        ),
        ConceptSpec(
            name="problem solving",
            difficulty="easy",
            question_types=["behavioral", "scenario"],
            key_points=[
                "structured approach to the problem",
                "alternatives considered",
                "result and learning",
            ],
            misconceptions=[],
            seeds={
                "behavioral": "Tell me about a difficult technical problem you solved and how you approached it.",
            },
        ),
        ConceptSpec(
            name="handling failure",
            difficulty="easy",
            question_types=["behavioral", "scenario"],
            key_points=[
                "owning the mistake",
                "what went wrong and why",
                "what you changed to prevent it",
            ],
            misconceptions=[],
            seeds={
                "behavioral": "Tell me about a production incident you caused or helped fix. What happened and what did you change?",
            },
        ),
        ConceptSpec(
            name="receiving feedback",
            difficulty="easy",
            question_types=["behavioral"],
            key_points=[
                "a concrete time you received hard feedback",
                "your reaction and action",
                "resulting change",
            ],
            misconceptions=[],
        ),
    ],
}


def concept_for(skill: str, concept_name: str) -> ConceptSpec | None:
    """Look up a concept spec by (skill, concept name), case-insensitively."""
    specs = CONCEPT_BANK.get(skill, [])
    for spec in specs:
        if spec.name.lower() == concept_name.strip().lower():
            return spec
    return None


def concepts_for_skill(skill: str) -> list[ConceptSpec]:
    """Return the concept specs registered for a skill (empty if unknown)."""
    return CONCEPT_BANK.get(skill, [])


def normalize_type(question_type: str) -> str:
    """Normalise a question type, mapping legacy aliases (e.g. conceptual)."""
    t = (question_type or "explanation").strip().lower()
    return QUESTION_TYPE_ALIASES.get(t, t)
