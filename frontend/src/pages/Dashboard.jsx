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

export default function Dashboard() {
  const [interviews, setInterviews] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    listInterviews()
      .then(setInterviews)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  return (
    <Layout>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500">Your past and ongoing interviews.</p>
        </div>
        <Link to="/interviews/new" className="btn-primary">
          + New Interview
        </Link>
      </div>

      {error && <ErrorBox message={error} />}
      {!interviews && !error && <Spinner />}

      {interviews && interviews.length === 0 && (
        <EmptyState
          title="No interviews yet"
          description="Create your first interview by pasting a job description and your resume. The AI will generate a personalized technical interview."
          action={
            <Link to="/interviews/new" className="btn-primary">
              Create an interview
            </Link>
          }
        />
      )}

      {interviews && interviews.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Target role</th>
                <th className="px-4 py-3">Level</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Progress</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {interviews.map((i) => (
                <tr key={i.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{i.target_role}</td>
                  <td className="px-4 py-3 text-slate-600">{i.experience_level}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                      {STATUS_LABELS[i.status] || i.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {i.answered_count}/{i.question_count}
                  </td>
                  <td className="px-4 py-3">
                    {i.report_overall_score != null ? (
                      <span className="font-semibold text-brand-600">
                        {i.report_overall_score}/10
                      </span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {new Date(i.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {i.status === "completed" ? (
                      <Link to={`/interviews/${i.id}/report`} className="font-medium text-brand-600 hover:underline">
                        Report →
                      </Link>
                    ) : (
                      <Link to={`/interviews/${i.id}`} className="font-medium text-brand-600 hover:underline">
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
    </Layout>
  );
}
