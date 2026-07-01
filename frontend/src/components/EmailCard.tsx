import type { EmailSession } from "../api";

interface Props {
  session: EmailSession;
}

const PRIORITY_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  Critical: { bg: "bg-red-100", text: "text-red-700", dot: "bg-red-500" },
  High:     { bg: "bg-orange-100", text: "text-orange-700", dot: "bg-orange-500" },
  Medium:   { bg: "bg-amber-100", text: "text-amber-700", dot: "bg-amber-500" },
  Low:      { bg: "bg-blue-100", text: "text-blue-700", dot: "bg-blue-400" },
  FYI:      { bg: "bg-slate-100", text: "text-slate-600", dot: "bg-slate-400" },
};

const TONE_STYLES: Record<string, string> = {
  formal:      "bg-indigo-50 text-indigo-700",
  casual:      "bg-green-50 text-green-700",
  urgent:      "bg-red-50 text-red-700",
  frustrated:  "bg-orange-50 text-orange-700",
  friendly:    "bg-teal-50 text-teal-700",
  neutral:     "bg-slate-50 text-slate-600",
};

export function EmailCard({ session }: Props) {
  const senderLabel = session.sender_name
    ? `${session.sender_name} <${session.sender_email}>`
    : session.sender_email;

  const receivedAt = new Date(session.created_at).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });

  const priorityStyle = session.priority_label
    ? (PRIORITY_STYLES[session.priority_label] ?? PRIORITY_STYLES["Medium"])
    : null;

  const toneStyle = session.detected_tone
    ? (TONE_STYLES[session.detected_tone] ?? TONE_STYLES["neutral"])
    : null;

  const tasks: string[] = session.identified_tasks
    ? (() => { try { return JSON.parse(session.identified_tasks); } catch { return []; } })()
    : [];

  const hasAnalysis = !!(session.priority_label || session.detected_tone || tasks.length > 0);

  return (
    <div className="flex flex-col h-full bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-6 py-5 border-b border-slate-100 bg-slate-50">
        <div className="flex items-center gap-2 mb-1">
          <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 text-sm font-semibold shrink-0">
            {(session.sender_name?.[0] ?? session.sender_email[0]).toUpperCase()}
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-800 truncate">{senderLabel}</p>
            <p className="text-xs text-slate-400">{receivedAt}</p>
          </div>
        </div>
        <h2 className="mt-3 text-base font-semibold text-slate-900 leading-snug">
          {session.subject ?? "(no subject)"}
        </h2>
      </div>

      {/* Agent Analysis Panel */}
      {hasAnalysis && (
        <div className="px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-indigo-50/60 to-slate-50/60">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 mb-3">
            Agent Analysis
          </p>

          <div className="flex flex-wrap gap-2 mb-3">
            {/* Priority badge */}
            {priorityStyle && session.priority_label && (
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${priorityStyle.bg} ${priorityStyle.text}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${priorityStyle.dot}`} />
                {session.priority_label} Priority
              </span>
            )}

            {/* Tone chip */}
            {toneStyle && session.detected_tone && (
              <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${toneStyle}`}>
                {session.detected_tone.charAt(0).toUpperCase() + session.detected_tone.slice(1)} tone
              </span>
            )}
          </div>

          {/* Tasks */}
          {tasks.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
                Action items
              </p>
              <ul className="space-y-1">
                {tasks.map((task, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-slate-600">
                    <span className="mt-1 w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                    {task}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Email body */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-3">
          Original Message
        </p>
        <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700 leading-relaxed">
          {session.original_body}
        </pre>
      </div>
    </div>
  );
}
