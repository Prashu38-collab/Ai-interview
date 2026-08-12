export default function ErrorBox({ message }) {
  if (!message) return null;
  return (
    <div className="flex items-start gap-3 rounded-xl border border-clay-200 bg-clay-50 px-4 py-3 text-sm text-clay-700">
      <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-clay-500 font-mono text-[11px] font-bold text-paper-50">
        !
      </span>
      <div className="min-w-0">{message}</div>
    </div>
  );
}
