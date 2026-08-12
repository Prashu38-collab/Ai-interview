import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../api/auth";
import { errorMessage } from "../api/client";
import ErrorBox from "../components/ErrorBox";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { access_token } = await login({ email, password });
      localStorage.setItem("token", access_token);
      navigate("/dashboard");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <aside className="hero-grain relative hidden overflow-hidden border-r border-paper-200 bg-paper lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div className="flex items-center gap-2.5">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-ink text-xl text-paper-card shadow-card">
            ◢
          </span>
          <span className="display text-2xl">
            Interview<span className="text-brand-600">Lab</span>
          </span>
        </div>
        <div className="max-w-md">
          <p className="eyebrow mb-4">AI-powered practice interviews</p>
          <h1 className="display text-5xl leading-[1.05]">
            Walk into your next technical interview with{" "}
            <span className="text-brand-600">confidence</span>.
          </h1>
          <p className="mt-5 text-base leading-relaxed text-ink-muted">
            Upload your resume, get a personalized question set, and receive
            instant, honest feedback on every answer.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {["Resume → questions", "Instant feedback", "Skill report"].map((t) => (
            <span key={t} className="chip border border-paper-300 bg-paper-card text-ink-muted">
              {t}
            </span>
          ))}
        </div>
      </aside>

      <main className="flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <span className="display text-2xl">
              Interview<span className="text-brand-600">Lab</span>
            </span>
          </div>
          <p className="eyebrow mb-2">Welcome back</p>
          <h2 className="display mb-6 text-3xl">Sign in to practice</h2>

          <form onSubmit={handleSubmit} className="card space-y-5">
            <div>
              <label className="label" htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
            <ErrorBox message={error} />
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? "Signing in…" : "Sign in"}
            </button>
            <p className="text-center text-sm text-ink-muted">
              No account?{" "}
              <Link to="/register" className="font-semibold text-brand-600 hover:underline">
                Create one
              </Link>
            </p>
          </form>
        </div>
      </main>
    </div>
  );
}
