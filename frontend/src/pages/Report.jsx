import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getReport } from "../api/interviews";
import { errorMessage } from "../api/client";
import Layout from "../components/Layout";
import Spinner from "../components/Spinner";
import ErrorBox from "../components/ErrorBox";

function scoreTone(score) {
  if (score >= 8) return "bg-sage-100 text-sage-600";
  if (score >= 5) return "bg-brand-100 text-brand-700";
  return "bg-clay-100 text-clay-700";
}

function barTone(score) {
  if (score >= 8) return "bg-sage-500";
  if (score >= 5) return "bg-brand-500";
  return "bg-clay-500";
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
  if (!report) return <Layout><Spinner label="Building report…" /></Layout>;

  const overallPct = Math.round((report.overall_score / 10) * 100);

  return (
    <Layout>
      <div className="mb-8">
        <p className="eyebrow mb-1">Generated {new Date(report.created_at).toLocaleString()}</p>
        <h1 className="display text-4xl">Interview report</h1>
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        <div className="card stagger flex flex-col items-center justify-center py-10" style={{ "--d": "0ms" }}>
          <div
            className="relative grid h-28 w-28 place-items-center rounded-full"
            style={{
              background: `conic-gradient(#CB6218 ${overallPct * 3.6}deg, #E9E1D2 0deg)`,
            }}
          >
            <div className="grid h-24 w-24 place-items-center rounded-full bg-paper-card">
              <div className="text-center">
                <div className="display text-3xl leading-none">{overallPct}%</div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-ink-faint">
                  overall
                </div>
              </div>
            </div>
          </div>
          <div className="mt-3 font-mono text-xs text-ink-muted">
            {report.overall_score}/10 average
          </div>
        </div>
        <div className="card stagger col-span-1 flex flex-col justify-center lg:col-span-2" style={{ "--d": "80ms" }}>
          <h3 className="eyebrow mb-2">Summary</h3>
          <p className="text-sm leading-relaxed text-ink-soft">{report.summary}</p>
        </div>
      </div>

      <div className="card stagger mb-6" style={{ "--d": "160ms" }}>
        <h3 className="mb-5 font-mono text-[11px] font-bold uppercase tracking-widest text-ink-muted">
          Skill-wise scores
        </h3>
        <div className="space-y-4">
          {report.skill_scores.map((s) => (
            <div key={s.skill} className="flex items-center gap-3">
              <span className="w-32 shrink-0 truncate text-sm font-semibold text-ink-soft">{s.skill}</span>
              <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-paper-200">
                <div
                  className={`h-full rounded-full animate-bar-fill ${barTone(s.score)}`}
                  style={{ width: `${(s.score / 10) * 100}%` }}
                />
              </div>
              <span className={`chip w-16 justify-center ${scoreTone(s.score)}`}>
                {s.score}/10
              </span>
              <span className="hidden w-24 text-right font-mono text-[10px] uppercase tracking-widest text-ink-faint sm:block">
                {s.question_count} q
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card stagger" style={{ "--d": "240ms" }}>
          <h3 className="mb-3 font-mono text-[11px] font-bold uppercase tracking-widest text-sage-600">
            Strengths
          </h3>
          <ul className="space-y-1.5 text-sm text-ink-soft">
            {report.strengths.map((s, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-sage-500">+</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="card stagger" style={{ "--d": "320ms" }}>
          <h3 className="mb-3 font-mono text-[11px] font-bold uppercase tracking-widest text-clay-600">
            Weaknesses
          </h3>
          <ul className="space-y-1.5 text-sm text-ink-soft">
            {report.weaknesses.map((w, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-clay-400">−</span>
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="card stagger" style={{ "--d": "400ms" }}>
          <h3 className="mb-3 font-mono text-[11px] font-bold uppercase tracking-widest text-brand-600">
            Recommended learning
          </h3>
          <ul className="space-y-1.5 text-sm text-ink-soft">
            {report.recommendations.map((r, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-brand-500">→</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Layout>
  );
}
