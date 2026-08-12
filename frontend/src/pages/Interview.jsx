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

const DIFFICULTY_COLORS = {
  easy: "bg-green-50 text-green-700",
  medium: "bg-amber-50 text-amber-700",
  hard: "bg-red-50 text-red-700",
};

export default function Interview() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [interview, setInterview] = useState(null);
  const [questions, setQuestions] = useState(null);
  const [current, setCurrent] = useState(null);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState(null); // evaluation of the current question
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
      await generateQuestions(id, interview.current_difficulty || "medium");
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
  if (!interview || !questions) return <Layout><Spinner /></Layout>;

  const answered = questions.filter((q) => q.status === "answered").length;
  const allDone = questions.length > 0 && answered === questions.length;
  const progress = questions.length ? Math.round((answered / questions.length) * 100) : 0;

  return (
    <Layout>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{interview.target_role}</h1>
          <p className="text-sm text-slate-500">
            {interview.experience_level} · {answered}/{questions.length} answered
            {interview.current_difficulty && (
              <span className="ml-2">
                · Next target difficulty:{" "}
                <span className="font-medium text-slate-700">{interview.current_difficulty}</span>
              </span>
            )}
          </p>
        </div>
        <button onClick={handleGenerate} className="btn-secondary" disabled={busy}>
          Regenerate questions
        </button>
      </div>

      <div className="mb-6">
        <div className="mb-1 flex justify-between text-xs text-slate-500">
          <span>Interview progress</span>
          <span>{progress}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
          <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${progress}%` }} />
        </div>
      </div>

      <ErrorBox message={error} />

      {questions.length === 0 && (
        <div className="card py-16 text-center">
          <div className="mb-3 text-4xl">🧠</div>
          <h2 className="text-lg font-semibold">No questions yet</h2>
          <p className="mb-4 text-sm text-slate-500">Generate your personalized questions to start.</p>
          <button onClick={handleGenerate} className="btn-primary" disabled={busy}>
            {busy ? "Generating…" : "Generate questions"}
          </button>
        </div>
      )}

      {current && (
        <div className="card">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${DIFFICULTY_COLORS[current.difficulty]}`}>
              {current.difficulty}
            </span>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
              {current.skill}
            </span>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
              {current.question_type}
            </span>
          </div>
          <h2 className="mb-1 text-lg font-semibold text-slate-900">{current.text}</h2>
          <p className="mb-4 text-xs text-slate-400">
            Key concepts expected: {current.expected_concepts.join(", ")}
          </p>

          {!result ? (
            <form onSubmit={handleSubmit}>
              <textarea
                className="input min-h-[140px]"
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
              <div className="flex items-center gap-4 rounded-lg bg-slate-50 p-4">
                <div className="text-3xl font-bold text-brand-600">{result.score}<span className="text-lg text-slate-400">/10</span></div>
                <p className="text-sm text-slate-600">{result.feedback}</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <h4 className="mb-1 text-sm font-semibold text-green-700">Strengths</h4>
                  <ul className="list-inside list-disc space-y-0.5 text-sm text-slate-600">
                    {result.strengths.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
                <div>
                  <h4 className="mb-1 text-sm font-semibold text-red-700">To improve</h4>
                  <ul className="list-inside list-disc space-y-0.5 text-sm text-slate-600">
                    {result.weaknesses.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              </div>
              {result.missing_concepts.length > 0 && (
                <p className="text-xs text-slate-500">
                  Missing concepts: {result.missing_concepts.join(", ")}
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
        <div className="card py-12 text-center">
          <div className="mb-3 text-4xl">🎉</div>
          <h2 className="text-lg font-semibold">All questions answered</h2>
          <p className="mb-4 text-sm text-slate-500">
            Complete the interview to generate your final report with skill-wise scores and recommendations.
          </p>
          <button onClick={handleComplete} className="btn-primary" disabled={busy}>
            {busy ? "Building report…" : "Complete interview & view report"}
          </button>
        </div>
      )}
    </Layout>
  );
}
