import { useEffect, useState } from "react";
import type { EmailSession } from "./api";
import { api } from "./api";
import { EmailCard } from "./components/EmailCard";
import { DraftReview } from "./components/DraftReview";

type AppState =
  | { phase: "loading" }
  | { phase: "empty" }
  | { phase: "fetching" }
  | { phase: "error"; message: string }
  | { phase: "review"; session: EmailSession };

export default function App() {
  const [state, setState] = useState<AppState>({ phase: "loading" });

  useEffect(() => {
    api
      .listDrafts()
      .then((sessions) => {
        const active = sessions.find((s) => s.status === "pending_review");
        const latest = active ?? sessions[0];
        if (latest) {
          setState({ phase: "review", session: latest });
        } else {
          setState({ phase: "empty" });
        }
      })
      .catch(() => setState({ phase: "empty" }));
  }, []);

  const handleFetch = async () => {
    setState({ phase: "fetching" });
    try {
      const res = await api.fetchEmail();
      setState({ phase: "review", session: res.session });
    } catch (err) {
      setState({
        phase: "error",
        message: err instanceof Error ? err.message : "Unexpected error.",
      });
    }
  };

  const handleSessionUpdate = (updated: EmailSession) => {
    setState({ phase: "review", session: updated });
  };

  const handleFetchAnother = () => setState({ phase: "empty" });

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 to-indigo-50 flex flex-col">
      {/* Navbar */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
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
            Stage 1
          </span>
        </div>

        {state.phase === "review" && state.session.status === "pending_review" && (
          <button
            onClick={handleFetchAnother}
            className="text-sm text-slate-500 hover:text-slate-800 transition"
          >
            ← Back
          </button>
        )}
      </header>

      {/* Main content */}
      <main className="flex-1 flex items-start justify-center p-6">
        {state.phase === "loading" && (
          <div className="flex flex-col items-center justify-center h-64 gap-4">
            <LoadingSpinner />
            <p className="text-sm text-slate-500">Loading sessions…</p>
          </div>
        )}

        {state.phase === "fetching" && (
          <div className="flex flex-col items-center justify-center h-64 gap-4 text-center">
            <LoadingSpinner />
            <div>
              <p className="text-base font-semibold text-slate-800">
                Fetching your email…
              </p>
              <p className="text-sm text-slate-500 mt-1">
                Claude is reading and drafting a reply. This takes a few seconds.
              </p>
            </div>
          </div>
        )}

        {state.phase === "empty" && (
          <div className="flex flex-col items-center justify-center h-64 gap-6 text-center max-w-sm">
            <div className="w-16 h-16 rounded-2xl bg-indigo-100 flex items-center justify-center">
              <svg
                className="w-8 h-8 text-indigo-500"
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
              <h2 className="text-lg font-semibold text-slate-900">No pending emails</h2>
              <p className="text-sm text-slate-500 mt-1">
                Click below to pull your oldest unread Gmail message and let the agent
                draft a reply.
              </p>
            </div>
            <button
              onClick={handleFetch}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 active:bg-indigo-800 shadow-sm transition"
            >
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
                  d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"
                />
              </svg>
              Fetch Email
            </button>
          </div>
        )}

        {state.phase === "error" && (
          <div className="flex flex-col items-center justify-center h-64 gap-4 text-center max-w-sm">
            <div className="w-14 h-14 rounded-2xl bg-red-100 flex items-center justify-center">
              <svg
                className="w-7 h-7 text-red-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                />
              </svg>
            </div>
            <div>
              <p className="text-base font-semibold text-red-700">Something went wrong</p>
              <p className="text-sm text-slate-500 mt-1">{state.message}</p>
            </div>
            <button
              onClick={() => setState({ phase: "empty" })}
              className="text-sm text-indigo-600 hover:text-indigo-800 font-medium transition"
            >
              Try again
            </button>
          </div>
        )}

        {state.phase === "review" && (
          <div className="w-full max-w-6xl">
            {/* Session status banner for completed sessions */}
            {state.session.status !== "pending_review" && (
              <div
                className={`mb-4 px-5 py-3 rounded-xl text-sm font-medium flex items-center gap-2 ${
                  state.session.status === "sent"
                    ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                    : "bg-slate-100 text-slate-600 border border-slate-200"
                }`}
              >
                {state.session.status === "sent" ? (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                    Reply sent successfully.
                  </>
                ) : (
                  "Draft discarded."
                )}
                <button
                  onClick={handleFetchAnother}
                  className="ml-auto underline underline-offset-2 text-current opacity-70 hover:opacity-100"
                >
                  Fetch another →
                </button>
              </div>
            )}

            {/* Two-panel layout */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5" style={{ height: "calc(100vh - 13rem)" }}>
              <EmailCard session={state.session} />
              <DraftReview
                session={state.session}
                onApproved={handleSessionUpdate}
                onDiscarded={handleSessionUpdate}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function LoadingSpinner() {
  return (
    <svg className="w-10 h-10 animate-spin text-indigo-400" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}
