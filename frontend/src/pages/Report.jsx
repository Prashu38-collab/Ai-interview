import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getReport } from "../api/interviews";
import { errorMessage } from "../api/client";
import Layout from "../components/Layout";
import Spinner from "../components/Spinner";
import ErrorBox from "../components/ErrorBox";

function scoreColor(score) {
  if (score >= 8) return "bg-green-100 text-green-800";
  if (score >= 5) return "bg-amber-100 text-amber-800";
  return "bg-red-100 text-red-800";
}

export default function Report() {
  const { id } = useParams();
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getReport(id)
      .then(setReport)
      .catch((err) => setError(errorMessage(err)));
  }, [id]);

  if (error) return <Layout><ErrorBox message={error} /></Layout>;
  if (!report) return <Layout><Spinner /></Layout>;

  const overallPct = Math.round((report.overall_score / 10) * 100);

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Interview Report</h1>
        <p className="text-sm text-slate-500">Generated {new Date(report.created_at).toLocaleString()}</p>
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <div className="card flex flex-col items-center justify-center py-8">
          <div className="text-4xl font-bold text-brand-600">{overallPct}%</div>
          <div className="text-sm text-slate-500">Overall score</div>
          <div className="mt-1 text-xs text-slate-400">({report.overall_score}/10 average)</div>
        </div>
        <div className="card col-span-2">
          <h3 className="mb-2 text-sm font-semibold text-slate-900">Summary</h3>
          <p className="text-sm text-slate-600">{report.summary}</p>
        </div>
      </div>

      <div className="card mb-6">
        <h3 className="mb-4 text-sm font-semibold text-slate-900">Skill-wise scores</h3>
        <div className="space-y-3">
          {report.skill_scores.map((s) => (
            <div key={s.skill} className="flex items-center gap-3">
              <span className="w-36 text-sm font-medium text-slate-700">{s.skill}</span>
              <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                <div
                  className={`h-full rounded-full ${scoreColor(s.score)}`}
                  style={{ width: `${(s.score / 10) * 100}%` }}
                />
              </div>
              <span className={`w-14 rounded-full px-2 py-0.5 text-center text-xs font-semibold ${scoreColor(s.score)}`}>
                {s.score}/10
              </span>
              <span className="w-20 text-xs text-slate-400">{s.question_count} question(s)</span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card">
          <h3 className="mb-2 text-sm font-semibold text-green-700">Strengths</h3>
          <ul className="list-inside list-disc space-y-1 text-sm text-slate-600">
            {report.strengths.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
        <div className="card">
          <h3 className="mb-2 text-sm font-semibold text-red-700">Weaknesses</h3>
          <ul className="list-inside list-disc space-y-1 text-sm text-slate-600">
            {report.weaknesses.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
        <div className="card">
          <h3 className="mb-2 text-sm font-semibold text-slate-900">Recommended learning</h3>
          <ul className="list-inside list-disc space-y-1 text-sm text-slate-600">
            {report.recommendations.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      </div>
    </Layout>
  );
}
