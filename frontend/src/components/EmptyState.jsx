export default function EmptyState({ title, description, action }) {
  return (
    <div className="card flex flex-col items-center gap-4 py-16 text-center">
      <div className="grid h-16 w-16 place-items-center rounded-2xl bg-brand-100 font-display text-3xl text-brand-600">
        ◇
      </div>
      <h3 className="display text-xl">{title}</h3>
      <p className="max-w-md text-sm leading-relaxed text-ink-muted">{description}</p>
      {action}
    </div>
  );
}
