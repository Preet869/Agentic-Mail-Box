import type { EmailSession } from "../api";

interface Props {
  sessions: EmailSession[];
  selectedId: string | null;
  onSelect: (session: EmailSession) => void;
  onSync: () => void;
  syncing: boolean;
}

const STATUS_DOT: Record<EmailSession["status"], string> = {
  pending_review: "bg-amber-400",
  sent: "bg-emerald-400",
  discarded: "bg-slate-300",
};

const STATUS_LABEL: Record<EmailSession["status"], string> = {
  pending_review: "Pending",
  sent: "Sent",
  discarded: "Discarded",
};

const PRIORITY_BADGE: Record<string, { bg: string; text: string }> = {
  Critical: { bg: "bg-red-100", text: "text-red-700" },
  High:     { bg: "bg-orange-100", text: "text-orange-700" },
  Medium:   { bg: "bg-amber-100", text: "text-amber-700" },
  Low:      { bg: "bg-blue-100", text: "text-blue-600" },
  FYI:      { bg: "bg-slate-100", text: "text-slate-500" },
};

function prioritySortValue(s: EmailSession): number {
  return s.priority_score ?? 0;
}

export function SessionSidebar({
  sessions,
  selectedId,
  onSelect,
  onSync,
  syncing,
}: Props) {
  const pending = sessions
    .filter((s) => s.status === "pending_review")
    .sort((a, b) => prioritySortValue(b) - prioritySortValue(a)); // highest priority first
  const done = sessions.filter((s) => s.status !== "pending_review");

  return (
    <aside className="flex flex-col h-full bg-white border-r border-slate-200 w-72 shrink-0">
      {/* Header */}
      <div className="px-4 py-4 border-b border-slate-100 flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">Inbox</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            {pending.length} pending · {done.length} done
          </p>
        </div>
        <button
          onClick={onSync}
          disabled={syncing}
          title="Sync inbox"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-50 disabled:cursor-not-allowed transition shrink-0"
        >
          {syncing ? (
            <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
          )}
          {syncing ? "Syncing…" : "Sync"}
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 && !syncing && (
          <div className="flex flex-col items-center justify-center h-40 gap-2 text-center px-6">
            <p className="text-sm text-slate-400">No sessions yet.</p>
            <p className="text-xs text-slate-400">Click Sync to fetch emails.</p>
          </div>
        )}

        {syncing && sessions.length === 0 && (
          <div className="flex items-center justify-center h-40">
            <svg className="w-6 h-6 animate-spin text-indigo-300" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
          </div>
        )}

        {pending.length > 0 && (
          <div>
            <p className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
              Pending
            </p>
            {pending.map((s) => (
              <SessionRow
                key={s.id}
                session={s}
                selected={s.id === selectedId}
                onSelect={onSelect}
              />
            ))}
          </div>
        )}

        {done.length > 0 && (
          <div>
            <p className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
              Completed
            </p>
            {done.map((s) => (
              <SessionRow
                key={s.id}
                session={s}
                selected={s.id === selectedId}
                onSelect={onSelect}
              />
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}

function SessionRow({
  session,
  selected,
  onSelect,
}: {
  session: EmailSession;
  selected: boolean;
  onSelect: (s: EmailSession) => void;
}) {
  const initial = (
    session.sender_name?.[0] ?? session.sender_email[0]
  ).toUpperCase();

  const senderLabel = session.sender_name ?? session.sender_email;

  const timeLabel = new Date(session.created_at).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <button
      onClick={() => onSelect(session)}
      className={`w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-slate-50 transition border-l-2 ${
        selected
          ? "bg-indigo-50 border-indigo-500"
          : "border-transparent"
      }`}
    >
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 ${
          selected
            ? "bg-indigo-200 text-indigo-800"
            : "bg-slate-100 text-slate-600"
        }`}
      >
        {initial}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-1">
          <span className="text-xs font-semibold text-slate-800 truncate">
            {senderLabel}
          </span>
          <span className="text-[10px] text-slate-400 shrink-0">{timeLabel}</span>
        </div>
        <p className="text-xs text-slate-500 truncate mt-0.5">
          {session.subject ?? "(no subject)"}
        </p>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          <div className="flex items-center gap-1">
            <span
              className={`w-1.5 h-1.5 rounded-full shrink-0 ${STATUS_DOT[session.status]}`}
            />
            <span className="text-[10px] text-slate-400">
              {STATUS_LABEL[session.status]}
            </span>
          </div>
          {session.priority_label && (() => {
            const style = PRIORITY_BADGE[session.priority_label] ?? PRIORITY_BADGE["Medium"];
            return (
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${style.bg} ${style.text}`}>
                {session.priority_label}
              </span>
            );
          })()}
        </div>
      </div>
    </button>
  );
}
