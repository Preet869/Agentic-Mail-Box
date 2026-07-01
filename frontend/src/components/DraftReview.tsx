import { useEffect, useRef, useState, useCallback } from "react";
import type { EmailSession } from "../api";
import { api } from "../api";

interface Props {
  session: EmailSession;
  onApproved: (updated: EmailSession) => void;
  onDiscarded: (updated: EmailSession) => void;
}

const STATUS_LABELS: Record<EmailSession["status"], string> = {
  pending_review: "Pending Review",
  sent: "Sent",
  discarded: "Discarded",
};

const STATUS_COLORS: Record<EmailSession["status"], string> = {
  pending_review: "bg-amber-100 text-amber-800",
  sent: "bg-emerald-100 text-emerald-800",
  discarded: "bg-slate-100 text-slate-600",
};

export function DraftReview({ session, onApproved, onDiscarded }: Props) {
  const [draftText, setDraftText] = useState(
    session.human_draft ?? session.agent_draft
  );
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const [approving, setApproving] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isReadOnly = session.status !== "pending_review";

  useEffect(() => {
    setDraftText(session.human_draft ?? session.agent_draft);
  }, [session.id, session.human_draft, session.agent_draft]);

  const handleTextChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value;
      setDraftText(value);
      setSaveState("saving");

      if (debounceTimer.current) clearTimeout(debounceTimer.current);
      debounceTimer.current = setTimeout(async () => {
        try {
          await api.updateDraft(session.id, value);
          setSaveState("saved");
          setTimeout(() => setSaveState("idle"), 1500);
        } catch {
          setSaveState("idle");
        }
      }, 600);
    },
    [session.id]
  );

  const handleApprove = async () => {
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
      await api.updateDraft(session.id, draftText).catch(() => null);
    }
    setError(null);
    setApproving(true);
    try {
      const res = await api.approveDraft(session.id);
      onApproved(res.session);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send email.");
    } finally {
      setApproving(false);
    }
  };

  const handleDiscard = async () => {
    setError(null);
    setDiscarding(true);
    try {
      const res = await api.discardDraft(session.id);
      onDiscarded(res.session);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to discard draft.");
    } finally {
      setDiscarding(false);
    }
  };

  const wordCount = draftText.trim().split(/\s+/).filter(Boolean).length;

  return (
    <div className="flex flex-col h-full bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-6 py-5 border-b border-slate-100 bg-slate-50 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1">
            Reply To
          </p>
          <p className="text-sm font-semibold text-slate-800">
            {session.sender_name
              ? `${session.sender_name} <${session.sender_email}>`
              : session.sender_email}
          </p>
          {session.subject && (
            <p className="text-xs text-slate-500 mt-0.5">
              Re: {session.subject}
            </p>
          )}
        </div>
        <span
          className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium shrink-0 ${STATUS_COLORS[session.status]}`}
        >
          {STATUS_LABELS[session.status]}
        </span>
      </div>

      {/* Agent badge */}
      {!isReadOnly && (
        <div className="px-6 pt-4 pb-0">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1 bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full font-medium">
              <svg
                className="w-3 h-3"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"
                />
              </svg>
              AI draft
            </span>
            <span>Edit freely — your changes auto-save</span>
          </div>
        </div>
      )}

      {/* Textarea */}
      <div className="flex-1 px-6 py-4 flex flex-col min-h-0">
        <textarea
          value={draftText}
          onChange={handleTextChange}
          readOnly={isReadOnly}
          className={`flex-1 w-full resize-none rounded-xl border text-sm leading-relaxed font-sans p-4 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition
            ${
              isReadOnly
                ? "bg-slate-50 border-slate-200 text-slate-600 cursor-default"
                : "bg-white border-slate-200 text-slate-800 hover:border-slate-300"
            }`}
          placeholder="Draft reply will appear here…"
          aria-label="Draft reply"
        />

        {/* Save indicator */}
        {!isReadOnly && (
          <div className="flex items-center justify-between mt-2 px-1">
            <span className="text-xs text-slate-400">{wordCount} words</span>
            <span
              className={`text-xs transition-opacity duration-300 ${
                saveState === "idle" ? "opacity-0" : "opacity-100"
              } ${saveState === "saved" ? "text-emerald-600" : "text-slate-400"}`}
            >
              {saveState === "saving" ? "Saving…" : "Saved"}
            </span>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mx-6 mb-2 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Action buttons */}
      {!isReadOnly && (
        <div className="px-6 py-5 border-t border-slate-100 flex gap-3">
          <button
            onClick={handleApprove}
            disabled={approving || discarding}
            className="flex-1 inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {approving ? (
              <>
                <Spinner />
                Sending…
              </>
            ) : (
              <>
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
                  />
                </svg>
                Approve &amp; Send
              </>
            )}
          </button>

          <button
            onClick={handleDiscard}
            disabled={approving || discarding}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl border border-slate-200 bg-white text-slate-700 text-sm font-semibold hover:bg-slate-50 hover:border-slate-300 active:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {discarding ? (
              <>
                <Spinner className="text-slate-400" />
                Discarding…
              </>
            ) : (
              "Discard"
            )}
          </button>
        </div>
      )}

      {/* Sent / discarded state */}
      {isReadOnly && (
        <div className="px-6 py-5 border-t border-slate-100 text-center">
          <p className="text-sm text-slate-500">
            {session.status === "sent"
              ? "This reply has been sent."
              : "This draft was discarded."}
          </p>
        </div>
      )}
    </div>
  );
}

function Spinner({ className = "text-white" }: { className?: string }) {
  return (
    <svg
      className={`w-4 h-4 animate-spin ${className}`}
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}
