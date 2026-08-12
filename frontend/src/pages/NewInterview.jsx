import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeInterview, createInterview, generateQuestions } from "../api/interviews";
import { errorMessage } from "../api/client";
import Layout from "../components/Layout";
import ErrorBox from "../components/ErrorBox";

const LEVELS = ["Entry Level", "Mid Level", "Senior Level"];

export default function NewInterview() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    target_role: "",
    experience_level: "Entry Level",
    job_description: "",
    resume_text: "",
    number_of_questions: 5,
  });
  const [phase, setPhase] = useState("form"); // form | analyzing | generating | done
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState("");

  function set(field) {
    return (e) => setForm({ ...form, [field]: e.target.value });
  }

  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    setPhase("analyzing");
    try {
      const interview = await createInterview(form);
      const a = await analyzeInterview(interview.id);
      setAnalysis(a);
      setPhase("generating");
      const result = await generateQuestions(interview.id, "medium");
      setPhase("done");
      navigate(`/interviews/${interview.id}`, { state: { generated: result.generated } });
    } catch (err) {
      setError(errorMessage(err));
      setPhase("form");
    }
  }

  return (
    <Layout>
      <h1 className="mb-1 text-2xl font-bold text-slate-900">New Interview</h1>
      <p className="mb-6 text-sm text-slate-500">
        Paste a job description and your resume. The AI analyzes them and builds a personalized interview.
      </p>

      {error && <ErrorBox message={error} />}

      <form onSubmit={handleCreate} className="card space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label">Target role</label>
            <input className="input" value={form.target_role} onChange={set("target_role")} required placeholder="e.g. Python Backend Developer" />
          </div>
          <div>
            <label className="label">Experience level</label>
            <select className="input" value={form.experience_level} onChange={set("experience_level")}>
              {LEVELS.map((l) => (
                <option key={l}>{l}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="label">Job description</label>
          <textarea className="input min-h-[120px]" value={form.job_description} onChange={set("job_description")} required placeholder="Paste the job description text here…" />
        </div>

        <div>
          <label className="label">Resume</label>
          <textarea className="input min-h-[120px]" value={form.resume_text} onChange={set("resume_text")} required placeholder="Paste your resume text here…" />
        </div>

        <div className="max-w-[200px]">
          <label className="label">Number of questions</label>
          <input type="number" min={1} max={20} className="input" value={form.number_of_questions} onChange={set("number_of_questions")} />
        </div>

        <button type="submit" className="btn-primary" disabled={phase !== "form"}>
          {phase === "form" && "Create & Analyze Interview"}
          {phase === "analyzing" && "Analyzing resume & job description…"}
          {phase === "generating" && "Generating interview questions…"}
          {phase === "done" && "Starting…"}
        </button>
      </form>

      {analysis && (
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <div className="card">
            <h3 className="mb-2 text-sm font-semibold text-slate-900">Your skills</h3>
            <div className="flex flex-wrap gap-1.5">
              {analysis.candidate_skills.map((s) => (
                <span key={s} className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                  {s}
                </span>
              ))}
            </div>
          </div>
          <div className="card">
            <h3 className="mb-2 text-sm font-semibold text-slate-900">Required by the role</h3>
            <div className="flex flex-wrap gap-1.5">
              {analysis.required_skills.map((s) => (
                <span key={s} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                  {s}
                </span>
              ))}
            </div>
          </div>
          <div className="card">
            <h3 className="mb-2 text-sm font-semibold text-slate-900">Skill gaps to focus on</h3>
            <div className="flex flex-wrap gap-1.5">
              {analysis.skill_gaps.length === 0 && <span className="text-xs text-slate-400">No gaps detected</span>}
              {analysis.skill_gaps.map((s) => (
                <span key={s} className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                  {s}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
