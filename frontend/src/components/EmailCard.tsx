import type { EmailSession } from "../api";

interface Props {
  session: EmailSession;
}

export function EmailCard({ session }: Props) {
  const senderLabel = session.sender_name
    ? `${session.sender_name} <${session.sender_email}>`
    : session.sender_email;

  const receivedAt = new Date(session.created_at).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });

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

      {/* Body */}
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
