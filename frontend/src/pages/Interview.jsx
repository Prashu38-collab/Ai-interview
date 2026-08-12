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

export default function Interview() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [interview, setInterview] = useState(null);
  const [questions, setQuestions] = useState(null);
  const [current, setCurrent] = useState(null);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState(null); // evaluation of the current question
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

  async function handleGenerate() {
    setBusy(true);
    setError("");
    try {
      await generateQuestions(id, interview.current_difficulty || "medium", true);
      setResult(null);
      setDuplicateWarning(null);
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
      setDuplicateWarning(res.duplicate_warning || null);
      setQuestions((qs) =>
        qs.map((q) => (q.id === current.id ? { ...q, status: "answered" } : q))
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function handleNext() {
    const pending = questions.find((q) => q.status === "pending");
    setCurrent(pending || null);
    setResult(null);
    setDuplicateWarning(null);
    setAnswer("");
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
            <div className="space-y-5">
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

              <div className="flex flex-col gap-4 rounded-xl bg-paper-50 p-5 sm:flex-row sm:items-center">
                <div
                  className={`grid h-20 w-20 shrink-0 place-items-center rounded-2xl border-2 ${
                    result.score >= 8
                      ? "border-sage-300 bg-sage-50"
                      : result.score >= 5
                        ? "border-brand-300 bg-brand-50"
                        : "border-clay-300 bg-clay-50"
                  }`}
                >
                  <div className="text-center">
                    <div className="display text-3xl leading-none">{result.score}</div>
                    <div className="font-mono text-[10px] uppercase tracking-widest text-ink-faint">
                      / 10
                    </div>
                  </div>
                </div>
                <div>
                  <p className="eyebrow mb-1">Feedback</p>
                  <p className="text-sm leading-relaxed text-ink-soft">{result.feedback}</p>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
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
                <div className="rounded-xl border border-clay-200 bg-clay-50 p-4">
                  <h4 className="mb-2 font-mono text-[11px] font-bold uppercase tracking-widest text-clay-600">
                    To improve
                  </h4>
                  <ul className="space-y-1 text-sm text-ink-soft">
                    {result.weaknesses.map((w, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-clay-400">−</span>
                        <span>{w}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {result.missing_concepts.length > 0 && (
                <p className="font-mono text-[11px] uppercase tracking-widest text-ink-faint">
                  Missing: {result.missing_concepts.join(" · ")}
                </p>
              )}

              <div className="flex justify-end">
                <button className="btn-primary" onClick={handleNext}>
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
