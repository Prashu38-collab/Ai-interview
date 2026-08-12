import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register } from "../api/auth";
import { errorMessage } from "../api/client";
import ErrorBox from "../components/ErrorBox";

export default function Register() {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { access_token } = await register({ email, full_name: fullName, password });
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
      <main className="flex items-center justify-center px-4 py-12 lg:order-1">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <span className="display text-2xl">
              Interview<span className="text-brand-600">Lab</span>
            </span>
          </div>
          <p className="eyebrow mb-2">New candidate</p>
          <h2 className="display mb-6 text-3xl">Create your account</h2>

          <form onSubmit={handleSubmit} className="card space-y-5">
            <div>
              <label className="label" htmlFor="fullName">Full name</label>
              <input
                id="fullName"
                className="input"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                minLength={1}
              />
            </div>
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
                minLength={8}
                autoComplete="new-password"
                placeholder="At least 8 characters"
              />
            </div>
            <ErrorBox message={error} />
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? "Creating account…" : "Create account"}
            </button>
            <p className="text-center text-sm text-ink-muted">
              Already registered?{" "}
              <Link to="/login" className="font-semibold text-brand-600 hover:underline">
                Sign in
              </Link>
            </p>
          </form>
        </div>
      </main>

      <aside className="hero-grain relative hidden overflow-hidden border-l border-paper-200 bg-paper lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div className="flex items-center gap-2.5">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-ink text-xl text-paper-card shadow-card">
            ◢
          </span>
          <span className="display text-2xl">
            Interview<span className="text-brand-600">Lab</span>
          </span>
        </div>
        <div className="max-w-md">
          <p className="eyebrow mb-4">Free. Honest. Personalized.</p>
          <h1 className="display text-5xl leading-[1.05]">
            Your resume, turned into a{" "}
            <span className="text-sage-600">mock interview</span> in seconds.
          </h1>
          <ul className="mt-6 space-y-3 text-sm text-ink-soft">
            {[
              "Questions written around your resume and the target role",
              "Adaptive difficulty that responds to how you perform",
              "A skill-by-skill report when you finish",
            ].map((f) => (
              <li key={f} className="flex items-start gap-3">
                <span className="mt-0.5 text-brand-600">✓</span>
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="font-mono text-[11px] uppercase tracking-widest text-ink-faint">
          No API key needed · runs fully offline in mock mode
        </div>
      </aside>
    </div>
  );
}
