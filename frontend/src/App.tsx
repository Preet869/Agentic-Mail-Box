import { useEffect, useState, useCallback } from "react";
import type { EmailSession } from "./api";
import { api } from "./api";
import { EmailCard } from "./components/EmailCard";
import { DraftReview } from "./components/DraftReview";
import { SessionSidebar } from "./components/SessionSidebar";

export default function App() {
  const [sessions, setSessions] = useState<EmailSession[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Merge incoming sessions into the existing list (update in-place or append)
  const mergeSessions = useCallback((incoming: EmailSession[]) => {
    setSessions((prev) => {
      const map = new Map(prev.map((s) => [s.id, s]));
      for (const s of incoming) map.set(s.id, s);
      return Array.from(map.values()).sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    });
  }, []);

  // Load existing sessions on mount
  useEffect(() => {
    api
      .listDrafts()
      .then((existing) => {
        mergeSessions(existing);
        const firstPending = existing.find((s) => s.status === "pending_review");
        setSelectedId(firstPending?.id ?? existing[0]?.id ?? null);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [mergeSessions]);

  const handleSync = async () => {
    setSyncing(true);
    setError(null);
    setSyncMessage(null);
    try {
      const res = await api.fetchEmails(10);
      mergeSessions(res.sessions);
      setSyncMessage(res.message);
      // Auto-select first newly pending session
      const firstNew = res.sessions.find((s) => s.status === "pending_review");
      if (firstNew) setSelectedId(firstNew.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed.");
    } finally {
      setSyncing(false);
    }
  };

  const handleSessionUpdate = useCallback((updated: EmailSession) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === updated.id ? updated : s))
    );
  }, []);

  const selectedSession = sessions.find((s) => s.id === selectedId) ?? null;

  return (
    <div className="h-screen flex flex-col bg-slate-50 overflow-hidden">
      {/* Navbar */}
      <header className="bg-white border-b border-slate-200 px-6 py-3.5 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
            <svg
              className="w-4 h-4 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75"
              />
            </svg>
          </div>
          <span className="font-semibold text-slate-900 text-lg">Agentic Mail Box</span>
          <span className="text-xs bg-indigo-100 text-indigo-600 px-2 py-0.5 rounded-full font-medium">
            Stage 3
          </span>
        </div>

        {/* Sync status message */}
        {syncMessage && !syncing && (
          <p className="text-xs text-slate-500 hidden sm:block">{syncMessage}</p>
        )}
        {error && (
          <p className="text-xs text-red-500 hidden sm:block">{error}</p>
        )}
      </header>

      {/* Body */}
      {loading ? (
        <div className="flex-1 flex items-center justify-center gap-4">
          <LoadingSpinner />
          <p className="text-sm text-slate-500">Loading sessions…</p>
        </div>
      ) : (
        <div className="flex-1 flex overflow-hidden">
          {/* Left: Session sidebar */}
          <SessionSidebar
            sessions={sessions}
            selectedId={selectedId}
            onSelect={(s) => setSelectedId(s.id)}
            onSync={handleSync}
            syncing={syncing}
          />

          {/* Right: Email detail — two panels */}
          {selectedSession ? (
            <div className="flex-1 grid grid-cols-2 gap-4 p-4 overflow-hidden min-w-0">
              <EmailCard session={selectedSession} />
              <DraftReview
                key={selectedSession.id}
                session={selectedSession}
                onApproved={handleSessionUpdate}
                onDiscarded={handleSessionUpdate}
              />
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center p-8">
              <div className="w-14 h-14 rounded-2xl bg-indigo-50 flex items-center justify-center">
                <svg
                  className="w-7 h-7 text-indigo-300"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M21.75 9v.906a2.25 2.25 0 01-1.183 1.981l-6.478 3.488M2.25 9v.906a2.25 2.25 0 001.183 1.981l6.478 3.488m8.839 2.51l-4.66-2.51m0 0l-1.023-.55a2.25 2.25 0 00-2.134 0l-1.022.55m0 0l-4.661 2.51m16.5 1.615a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V8.844a2.25 2.25 0 011.183-1.981l7.5-4.039a2.25 2.25 0 012.134 0l7.5 4.039a2.25 2.25 0 011.183 1.98V19.5z"
                  />
                </svg>
              </div>
              <div>
                <p className="text-base font-semibold text-slate-700">No email selected</p>
                <p className="text-sm text-slate-400 mt-1">
                  Click <strong>Sync</strong> to fetch your inbox, then select an email from the sidebar.
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function LoadingSpinner() {
  return (
    <svg className="w-8 h-8 animate-spin text-indigo-400" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}
