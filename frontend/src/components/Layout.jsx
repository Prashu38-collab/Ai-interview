import { Link, NavLink, useNavigate } from "react-router-dom";

export default function Layout({ children }) {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("user") || "null");

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate("/login");
  }

  const navLink = ({ isActive }) =>
    `rounded-lg px-3 py-1.5 font-mono text-xs font-semibold uppercase tracking-widest transition ${
      isActive
        ? "bg-brand-100 text-brand-700"
        : "text-ink-muted hover:bg-paper-100 hover:text-ink"
    }`;

  return (
    <div className="flex min-h-screen flex-col">
      <div className="h-1 w-full bg-gradient-to-r from-brand-500 via-brand-300 to-sage-500" />
      <header className="border-b border-paper-200 bg-paper/70 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3.5">
          <Link to="/dashboard" className="group flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-ink text-lg text-paper-card shadow-card transition group-hover:-rotate-6 group-hover:bg-brand-600">
              ◢
            </span>
            <span className="display text-xl leading-none">
              Interview<span className="text-brand-600">Lab</span>
            </span>
          </Link>
          <nav className="flex items-center gap-1.5">
            <NavLink to="/dashboard" className={navLink}>
              Dashboard
            </NavLink>
            <NavLink to="/interviews/new" className={navLink}>
              New interview
            </NavLink>
            <span className="mx-2 h-4 w-px bg-paper-300" />
            <span className="max-w-[120px] truncate text-sm font-semibold text-ink-soft">
              {user?.full_name}
            </span>
            <button
              onClick={logout}
              className="ml-1 rounded-lg px-2.5 py-1.5 font-mono text-xs font-semibold uppercase tracking-widest text-ink-muted transition hover:bg-clay-50 hover:text-clay-600"
            >
              Sign out
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
      <footer className="mx-auto max-w-6xl px-4 pb-6 text-center font-mono text-[11px] uppercase tracking-widest text-ink-faint">
        InterviewLab — FastAPI · PostgreSQL · React · LLM
      </footer>
    </div>
  );
}
