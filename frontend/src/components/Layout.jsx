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
    `rounded-lg px-3 py-2 text-sm font-medium transition ${
      isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
    }`;

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Link to="/dashboard" className="flex items-center gap-2 text-lg font-bold text-brand-600">
            <span className="text-2xl">🤖</span> AI Interviewer
          </Link>
          <nav className="flex items-center gap-1">
            <NavLink to="/dashboard" className={navLink}>
              Dashboard
            </NavLink>
            <NavLink to="/interviews/new" className={navLink}>
              New Interview
            </NavLink>
            <span className="mx-2 h-5 w-px bg-slate-200" />
            <span className="text-sm text-slate-500">{user?.full_name}</span>
            <button onClick={logout} className="ml-2 text-sm font-medium text-slate-500 hover:text-red-600">
              Sign out
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      <footer className="mx-auto max-w-5xl px-4 pb-8 text-center text-xs text-slate-400">
        AI Interviewer — a portfolio project demonstrating FastAPI, PostgreSQL, React and LLM integration.
      </footer>
    </div>
  );
}
