import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  completeInterview,
  generateQuestions,
  getInterview,
  getQuestions,
  submitAnswer,
} from "../api/interviews";
import { errorMessage } from "../api/client";
import Layout from "../components/Layout";
import Spinner from "../components/Spinner";
import ErrorBox from "../components/ErrorBox";

const DIFFICULTY_STYLE = {
  easy: "bg-sage-100 text-sage-600",
  medium: "bg-brand-100 text-brand-700",
  hard: "bg-clay-100 text-clay-700",
};

const REQ_TONES = {
  sage: { box: "border-sage-200 bg-sage-50", head: "text-sage-600", mark: "text-sage-500" },
  brand: { box: "border-brand-200 bg-brand-50", head: "text-brand-700", mark: "text-brand-500" },
  clay: { box: "border-clay-200 bg-clay-50", head: "text-clay-600", mark: "text-clay-400" },
};

function RequirementList({ title, items, tone }) {
  if (!items || items.length === 0) return null;
  const t = REQ_TONES[tone];
  return (
    <div className={`rounded-xl border p-4 ${t.box}`}>
      <h4 className={`mb-2 font-mono text-[11px] font-bold uppercase tracking-widest ${t.head}`}>
        {title}
      </h4>
      <ul className="space-y-1 text-sm text-ink-soft">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2">
            <span className={t.mark}>·</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function scoreTone(score) {
  if (score >= 8) return "border-sage-300 bg-sage-50";
  if (score >= 5) return "border-brand-300 bg-brand-50";
  return "border-clay-300 bg-clay-50";
}

export default function Interview() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [interview, setInterview] = useState(null);
  const [questions, setQuestions] = useState(null);
  const [current, setCurrent] = useState(null);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState(null); // evaluation of the current question
  const [followUp, setFollowUp] = useState(null); // queued follow-up question (QuestionOut)
  const [duplicateWarning, setDuplicateWarning] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [iv, qs] = await Promise.all([getInterview(id), getQuestions(id)]);
      setInterview(iv);
      setQuestions(qs);
      const pending = qs.find((q) => q.status === "pending");
      setCurrent(pending || null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function refreshQuestions() {
    try {
      const qs = await getQuestions(id);
      setQuestions(qs);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function handleGenerate() {
    setBusy(true);
    setError("");
    try {
      await generateQuestions(id, interview.current_difficulty || "medium", true);
      setResult(null);
      setDuplicateWarning(null);
      setFollowUp(null);
      setAnswer("");
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!answer.trim()) return;
    setBusy(true);
    setError("");
    try {
      const res = await submitAnswer(current.id, answer);
      setResult(res.evaluation);
      setFollowUp(res.follow_up || null);
      setDuplicateWarning(res.duplicate_warning || null);
      setQuestions((qs) =>
        qs.map((q) => (q.id === current.id ? { ...q, status: "answered" } : q))
      );
      await refreshQuestions(); // include any newly queued follow-up question
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function handleNext() {
    // Prefer a queued follow-up whose parent was already answered, matching
    // the server's next_pending() ordering.
    const followUpPending = questions.find(
      (q) =>
        q.status === "pending" &&
        q.follow_up_of != null &&
        questions.some((p) => p.id === q.follow_up_of && p.status === "answered")
    );
    const pending = followUpPending || questions.find((q) => q.status === "pending");
    setCurrent(pending || null);
    setResult(null);
    setFollowUp(null);
    setDuplicateWarning(null);
    setAnswer("");
  }

  function handleFollowUp() {
    if (!followUp) return;
    setCurrent(followUp);
    setResult(null);
    setDuplicateWarning(null);
    setAnswer("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleComplete() {
    setBusy(true);
    setError("");
    try {
      await completeInterview(id);
      navigate(`/interviews/${id}/report`);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  if (error && !interview) return <Layout><ErrorBox message={error} /></Layout>;
  if (!interview || !questions) return <Layout><Spinner label="Loading interview…" /></Layout>;

  const answered = questions.filter((q) => q.status === "answered").length;
  const progress = questions.length ? Math.round((answered / questions.length) * 100) : 0;

  const corrections = [
    ...(result?.technical_errors || []),
    ...(result?.misconceptions || []),
    ...(result?.contradictions || []),
  ].filter((c, i, arr) => arr.indexOf(c) === i);

  return (
    <Layout>
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <p className="eyebrow mb-1">
            {interview.experience_level} · {answered}/{questions.length} answered
            {interview.current_difficulty && ` · next: ${interview.current_difficulty}`}
          </p>
          <h1 className="display text-3xl">{interview.target_role}</h1>
        </div>
        <button onClick={handleGenerate} className="btn-secondary" disabled={busy}>
          {busy ? "Regenerating…" : "⟳ Fresh questions"}
        </button>
      </div>

      <div className="mb-8">
        <div className="mb-1.5 flex justify-between font-mono text-[11px] font-semibold uppercase tracking-widest text-ink-muted">
          <span>Interview progress</span>
          <span>{progress}%</span>
        </div>
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-paper-200">
          <div
            className="h-full rounded-full bg-gradient-to-r from-brand-500 to-brand-400 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <ErrorBox message={error} />

      {questions.length === 0 && (
        <div className="card flex flex-col items-center gap-4 py-16 text-center">
          <div className="grid h-16 w-16 place-items-center rounded-2xl bg-brand-100 font-display text-3xl text-brand-600">
            ✦
          </div>
          <h2 className="display text-2xl">No questions yet</h2>
          <p className="max-w-md text-sm text-ink-muted">
            Generate your personalized questions to start the interview.
          </p>
          <button onClick={handleGenerate} className="btn-primary" disabled={busy}>
            {busy ? "Generating…" : "Generate questions"}
          </button>
        </div>
      )}

      {current && (
        <div className="card stagger space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`chip ${DIFFICULTY_STYLE[current.difficulty]}`}>
              {current.difficulty}
            </span>
            <span className="chip bg-ink text-paper-50">{current.skill}</span>
            <span className="chip border border-paper-300 bg-paper-card text-ink-muted">
              {current.question_type}
            </span>
            {current.follow_up_of != null && (
              <span className="chip border border-brand-300 bg-brand-50 text-brand-700">
                follow-up
              </span>
            )}
          </div>
          <h2 className="display text-2xl leading-snug">{current.text}</h2>
          <p className="font-mono text-[11px] uppercase tracking-widest text-ink-faint">
            Expected: {current.expected_concepts.join(" · ")}
          </p>

          {!result ? (
            <form onSubmit={handleSubmit}>
              <textarea
                className="input min-h-[150px]"
                placeholder="Write your answer here. Be specific and use technical terms."
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
              />
              <div className="mt-4 flex justify-end">
                <button type="submit" className="btn-primary" disabled={busy || !answer.trim()}>
                  {busy ? "Evaluating…" : "Submit answer"}
                </button>
              </div>
            </form>
          ) : (
            <div className="space-y-4">
              {duplicateWarning && (
                <div className="flex items-start gap-3 rounded-xl border border-brand-300 bg-brand-50 px-4 py-3 text-sm text-brand-800">
                  <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand-500 font-mono text-[11px] font-bold text-paper-50">
                    !
                  </span>
                  <div>
                    <p className="font-bold">Similar answer detected</p>
                    <p className="mt-0.5">{duplicateWarning}</p>
                  </div>
                </div>
              )}

              {/* Coaching-first feedback: prose first, score secondary. */}
              <div className="flex items-start justify-between gap-4 rounded-xl bg-paper-50 p-5">
                <div className="min-w-0 space-y-1.5">
                  <p className="eyebrow mb-1">Coaching feedback</p>
                  <p className="text-sm leading-relaxed text-ink-soft">{result.feedback}</p>
                  <div className="flex flex-wrap gap-2 pt-1">
                    <span className="chip border border-paper-300 bg-paper-card text-ink-muted">
                      {result.answer_status}
                    </span>
                    {result.follow_up_question && (
                      <span className="chip border border-brand-300 bg-brand-50 text-brand-700">
                        ⇢ targeted follow-up queued
                      </span>
                    )}
                  </div>
                </div>
                <div className="shrink-0">
                  <div
                    className={`grid h-16 w-16 place-items-center rounded-2xl border-2 ${scoreTone(result.score)}`}
                  >
                    <div className="text-center">
                      <div className="display text-2xl leading-none">{result.score}</div>
                      <div className="font-mono text-[9px] uppercase tracking-widest text-ink-faint">
                        / 10
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {result.strengths.length > 0 && (
                <div className="rounded-xl border border-sage-200 bg-sage-50 p-4">
                  <h4 className="mb-2 font-mono text-[11px] font-bold uppercase tracking-widest text-sage-600">
                    Strengths
                  </h4>
                  <ul className="space-y-1 text-sm text-ink-soft">
                    {result.strengths.map((s, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-sage-500">+</span>
                        <span>{s}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="grid gap-4 sm:grid-cols-2">
                <RequirementList
                  title="Demonstrated"
                  items={result.satisfied_requirements}
                  tone="sage"
                />
                <RequirementList
                  title="Partially covered"
                  items={result.partial_requirements}
                  tone="brand"
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <RequirementList
                  title="Not yet covered"
                  items={result.missing_requirements}
                  tone="clay"
                />
                <RequirementList title="To correct" items={corrections} tone="clay" />
              </div>

              {followUp && (
                <div className="rounded-xl border border-brand-300 bg-brand-50 p-4">
                  <p className="eyebrow mb-1 text-brand-700">Targeted follow-up</p>
                  <p className="text-sm leading-relaxed text-ink-soft">{followUp.text}</p>
                  <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-brand-600">
                    Deepens {followUp.concept} · {followUp.question_type} · {followUp.difficulty}
                  </p>
                  <div className="mt-3 flex justify-end">
                    <button className="btn-primary" onClick={handleFollowUp} disabled={busy}>
                      Answer follow-up →
                    </button>
                  </div>
                </div>
              )}

              <div className="flex justify-end">
                <button className="btn-secondary" onClick={handleNext}>
                  Next question →
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {!current && questions.length > 0 && (
        <div className="card flex flex-col items-center gap-4 py-14 text-center">
          <div className="grid h-16 w-16 place-items-center rounded-2xl bg-sage-100 font-display text-3xl text-sage-600">
            ✓
          </div>
          <h2 className="display text-2xl">All questions answered</h2>
          <p className="max-w-md text-sm text-ink-muted">
            Complete the interview to generate your final report with skill-wise
            scores and recommendations.
          </p>
          <button onClick={handleComplete} className="btn-primary" disabled={busy}>
            {busy ? "Building report…" : "Complete interview & view report"}
          </button>
        </div>
      )}
    </Layout>
  );
}
