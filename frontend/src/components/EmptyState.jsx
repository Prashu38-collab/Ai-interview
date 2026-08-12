export default function EmptyState({ title, description, action }) {
  return (
    <div className="card flex flex-col items-center gap-3 py-16 text-center">
      <div className="text-4xl">🎯</div>
      <h3 className="text-lg font-semibold text-slate-800">{title}</h3>
      <p className="max-w-md text-sm text-slate-500">{description}</p>
      {action}
    </div>
  );
}
