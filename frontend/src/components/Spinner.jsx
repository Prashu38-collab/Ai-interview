export default function Spinner({ label = "Loading…" }) {
  return (
    <div className="flex flex-col items-center gap-3 py-14">
      <div className="h-9 w-9 animate-spin rounded-full border-[3px] border-brand-200 border-t-brand-600" />
      <span className="font-mono text-[11px] font-semibold uppercase tracking-widest text-ink-muted">
        {label}
      </span>
    </div>
  );
}
