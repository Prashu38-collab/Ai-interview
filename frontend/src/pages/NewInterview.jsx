import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeInterview, createInterview, extractResume, generateQuestions } from "../api/interviews";
import { errorMessage } from "../api/client";
import Layout from "../components/Layout";
import ErrorBox from "../components/ErrorBox";

const LEVELS = ["Entry Level", "Mid Level", "Senior Level"];

export default function NewInterview() {
  const navigate = useNavigate();
  const fileRef = useRef(null);
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
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState(null);
  const [dragging, setDragging] = useState(false);

  function set(field) {
    return (e) => setForm({ ...form, [field]: e.target.value });
  }

  async function handleFile(file) {
    if (!file) return;
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please choose a PDF file.");
      return;
    }
    setError("");
    setUploading(true);
    try {
      const { text, filename } = await extractResume(file);
      setFileName(filename);
      setForm((f) => ({ ...f, resume_text: text }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
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

  const resumeValid = form.resume_text.trim().length >= 10;

  return (
    <Layout>
      <div className="mb-8">
        <p className="eyebrow mb-1">Setup</p>
        <h1 className="display text-4xl">New interview</h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-muted">
          Upload your resume as a PDF (or paste its text) plus the job
          description. The AI analyzes both and builds a question set written
          around your profile.
        </p>
      </div>

      {error && <ErrorBox message={error} />}

      <form onSubmit={handleCreate} className="card space-y-6">
        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="role">Target role</label>
            <input
              id="role"
              className="input"
              value={form.target_role}
              onChange={set("target_role")}
              required
              placeholder="e.g. Python Backend Developer"
            />
          </div>
          <div>
            <label className="label" htmlFor="level">Experience level</label>
            <select id="level" className="input" value={form.experience_level} onChange={set("experience_level")}>
              {LEVELS.map((l) => (
                <option key={l}>{l}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="label" htmlFor="jd">Job description</label>
          <textarea
            id="jd"
            className="input min-h-[120px]"
            value={form.job_description}
            onChange={set("job_description")}
            required
            placeholder="Paste the job description text here…"
          />
        </div>

        <div>
          <label className="label">Resume</label>
          <div
            className={`grid gap-3 rounded-xl border-2 border-dashed p-4 transition sm:grid-cols-2 ${
              dragging ? "border-brand-500 bg-brand-50" : "border-paper-300 bg-paper-50"
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              handleFile(e.dataTransfer.files?.[0]);
            }}
          >
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="flex flex-col items-center justify-center gap-2 rounded-lg border border-paper-200 bg-paper-card px-4 py-6 text-center transition hover:border-brand-400 hover:bg-brand-50 disabled:opacity-50"
            >
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-100 text-lg text-brand-600">⬆</span>
              <span className="text-sm font-semibold text-ink-soft">
                {uploading ? "Extracting text…" : "Upload PDF resume"}
              </span>
              <span className="font-mono text-[10px] uppercase tracking-widest text-ink-faint">
                .pdf · max 5 MB
              </span>
            </button>
            <div className="flex flex-col justify-center gap-2">
              <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-ink-faint">
                Or paste text directly
              </span>
              <textarea
                className="input min-h-[90px]"
                value={form.resume_text}
                onChange={set("resume_text")}
                required
                placeholder="Paste your resume text here…"
              />
            </div>
          </div>
          {fileName && (
            <p className="mt-2 flex items-center gap-2 font-mono text-[11px] text-sage-600">
              <span>✓</span> Extracted from {fileName}
              <span className="text-ink-faint">
                · {form.resume_text.trim().split(/\s+/).length} words
              </span>
            </p>
          )}
          {!resumeValid && (
            <p className="mt-2 text-xs text-clay-600">
              Add at least 10 characters of resume content so the AI can analyze it.
            </p>
          )}
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
        </div>

        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-[200px]">
            <label className="label" htmlFor="count">Number of questions</label>
            <input
              id="count"
              type="number"
              min={1}
              max={20}
              className="input"
              value={form.number_of_questions}
              onChange={set("number_of_questions")}
            />
          </div>
          <button type="submit" className="btn-primary" disabled={phase !== "form" || !resumeValid}>
            {phase === "form" && "Create & analyze interview"}
            {phase === "analyzing" && "Analyzing resume & job description…"}
            {phase === "generating" && "Writing your questions…"}
            {phase === "done" && "Starting…"}
          </button>
        </div>
      </form>

      {analysis && (
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          {[
            { title: "Skills we spotted", items: analysis.candidate_skills, tone: "bg-brand-100 text-brand-700" },
            { title: "Required by the role", items: analysis.required_skills, tone: "bg-paper-200 text-ink-soft" },
            { title: "Gaps to focus on", items: analysis.skill_gaps, tone: "bg-clay-100 text-clay-700", empty: "No gaps detected" },
          ].map((c, i) => (
            <div key={c.title} className="card stagger" style={{ "--d": `${i * 80}ms` }}>
              <h3 className="mb-2 font-mono text-[11px] font-bold uppercase tracking-widest text-ink-muted">
                {c.title}
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {c.items.length === 0 && <span className="text-xs text-ink-faint">{c.empty || "—"}</span>}
                {c.items.map((s) => (
                  <span key={s} className={`chip ${c.tone}`}>{s}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}
