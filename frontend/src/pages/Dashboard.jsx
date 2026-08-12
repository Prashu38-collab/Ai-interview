import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listInterviews } from "../api/interviews";
import { errorMessage } from "../api/client";
import Layout from "../components/Layout";
import Spinner from "../components/Spinner";
import ErrorBox from "../components/ErrorBox";
import EmptyState from "../components/EmptyState";

const STATUS_LABELS = {
  created: "Draft",
  ready: "Ready",
  in_progress: "In progress",
  completed: "Completed",
};

const STATUS_STYLE = {
  created: "bg-paper-200 text-ink-muted",
  ready: "bg-brand-100 text-brand-700",
  in_progress: "bg-sage-100 text-sage-600",
  completed: "bg-ink text-paper-50",
};

function scoreTone(score) {
  if (score >= 8) return "text-sage-600";
  if (score >= 5) return "text-brand-600";
  return "text-clay-600";
}

export default function Dashboard() {
  const [interviews, setInterviews] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    listInterviews()
      .then(setInterviews)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  const total = interviews?.length ?? 0;
  const inProgress = interviews?.filter((i) => i.status === "in_progress").length ?? 0;
  const completed = interviews?.filter((i) => i.status === "completed").length ?? 0;
  const scores = interviews?.map((i) => i.report_overall_score).filter((s) => s != null) ?? [];
  const avgScore = scores.length
    ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1)
    : "—";

  const stats = [
    { label: "Interviews", value: total, hint: "total created" },
    { label: "In progress", value: inProgress, hint: "active sessions" },
    { label: "Completed", value: completed, hint: "with reports" },
    { label: "Avg. score", value: avgScore, hint: "across reports" },
  ];

  return (
    <Layout>
      <div className="mb-8 flex items-end justify-between gap-4">
        <div>
          <p className="eyebrow mb-1">Overview</p>
          <h1 className="display text-4xl">Dashboard</h1>
        </div>
        <Link to="/interviews/new" className="btn-primary">
          <span aria-hidden>+</span> New interview
        </Link>
      </div>

      {error && <ErrorBox message={error} />}
      {!interviews && !error && <Spinner label="Loading interviews…" />}

      {interviews && (
        <>
          <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
            {stats.map((s, i) => (
              <div
                key={s.label}
                className="card stagger p-5"
                style={{ "--d": `${i * 70}ms` }}
              >
                <p className="font-mono text-[10px] font-bold uppercase tracking-widest text-ink-faint">
                  {s.label}
                </p>
                <p className="display mt-1.5 text-3xl">{s.value}</p>
                <p className="mt-0.5 text-xs text-ink-muted">{s.hint}</p>
              </div>
            ))}
          </div>

          {interviews.length === 0 ? (
            <EmptyState
              title="No interviews yet"
              description="Create your first interview by pasting a job description and uploading your resume as a PDF. The AI builds a personalized question set around both."
              action={
                <Link to="/interviews/new" className="btn-primary">
                  Create an interview
                </Link>
              }
            />
          ) : (
            <div className="card overflow-hidden p-0">
              <div className="flex items-center justify-between border-b border-paper-200 px-6 py-4">
                <h2 className="display text-lg">Interview history</h2>
                <span className="font-mono text-[11px] uppercase tracking-widest text-ink-faint">
                  {total} record{total === 1 ? "" : "s"}
                </span>
              </div>
              <table className="w-full text-left text-sm">
                <thead className="border-b border-paper-200 bg-paper-50 font-mono text-[10px] uppercase tracking-widest text-ink-faint">
                  <tr>
                    <th className="px-6 py-3">Target role</th>
                    <th className="hidden px-4 py-3 md:table-cell">Level</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="hidden px-4 py-3 sm:table-cell">Progress</th>
                    <th className="px-4 py-3">Score</th>
                    <th className="px-6 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-paper-100">
                  {interviews.map((i) => (
                    <tr key={i.id} className="stagger transition-colors hover:bg-paper-50" style={{ "--d": "0ms" }}>
                      <td className="px-6 py-4 font-semibold text-ink">{i.target_role}</td>
                      <td className="hidden px-4 py-4 text-ink-muted md:table-cell">
                        {i.experience_level}
                      </td>
                      <td className="px-4 py-4">
                        <span className={`chip ${STATUS_STYLE[i.status] || "bg-paper-200 text-ink-muted"}`}>
                          {STATUS_LABELS[i.status] || i.status}
                        </span>
                      </td>
                      <td className="hidden px-4 py-4 font-mono text-xs text-ink-muted sm:table-cell">
                        {i.question_count === 0
                          ? "—"
                          : `${i.answered_count}/${i.question_count}`}
                      </td>
                      <td className="px-4 py-4">
                        {i.report_overall_score != null ? (
                          <span className={`font-mono text-sm font-bold ${scoreTone(i.report_overall_score)}`}>
                            {i.report_overall_score}/10
                          </span>
                        ) : (
                          <span className="font-mono text-xs text-ink-faint">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right">
                        {i.status === "completed" ? (
                          <Link
                            to={`/interviews/${i.id}/report`}
                            className="font-mono text-xs font-bold uppercase tracking-widest text-brand-600 transition hover:text-brand-500"
                          >
                            Report →
                          </Link>
                        ) : (
                          <Link
                            to={`/interviews/${i.id}`}
                            className="font-mono text-xs font-bold uppercase tracking-widest text-brand-600 transition hover:text-brand-500"
                          >
                            Open →
                          </Link>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </Layout>
  );
}
