/**
 * Typed API client for the Agentic Mail Box backend.
 * All requests go to /api (proxied to http://localhost:8000 by Vite).
 */

export type SessionStatus = "pending_review" | "sent" | "discarded";

export interface EmailSession {
  id: string;
  gmail_id: string;
  sender_name: string | null;
  sender_email: string;
  subject: string | null;
  original_body: string;
  agent_draft: string;
  human_draft: string | null;
  status: SessionStatus;
  created_at: string;
  actioned_at: string | null;

  // Stage 3 — agentic analysis fields
  priority_score: number | null;       // 1–5
  priority_label: string | null;       // "Critical" | "High" | "Medium" | "Low" | "FYI"
  detected_tone: string | null;        // "formal" | "casual" | "urgent" | etc.
  identified_tasks: string | null;     // JSON-encoded string[]
  agent_draft_v1: string | null;       // draft before self-correction
  self_critique: string | null;        // JSON-encoded string[] of issues

  // Stage 4 — tool use
  tools_used: string | null;           // JSON-encoded Array<{tool, args, result}>
}

export interface FetchEmailResponse {
  session: EmailSession;
  message: string;
}

export interface ApproveResponse {
  session: EmailSession;
  message: string;
}

export interface DiscardResponse {
  session: EmailSession;
  message: string;
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(
      typeof error.detail === "string" ? error.detail : JSON.stringify(error.detail)
    );
  }

  return res.json() as Promise<T>;
}

export interface FetchBatchResponse {
  sessions: EmailSession[];
  fetched: number;
  skipped: number;
  message: string;
}

export const api = {
  /** Fetch the oldest unread Gmail + generate an agent draft. */
  fetchEmail(): Promise<FetchEmailResponse> {
    return request<FetchEmailResponse>("/email/fetch");
  },

  /** Fetch up to max_results unread emails and generate drafts for all new ones. */
  fetchEmails(maxResults = 10): Promise<FetchBatchResponse> {
    return request<FetchBatchResponse>(`/emails/fetch-batch?max_results=${maxResults}`);
  },

  /** List all stored sessions, newest first. */
  listDrafts(): Promise<EmailSession[]> {
    return request<EmailSession[]>("/drafts");
  },

  /** Get a single session by ID. */
  getDraft(id: string): Promise<EmailSession> {
    return request<EmailSession>(`/drafts/${id}`);
  },

  /** Auto-save the human-edited draft. */
  updateDraft(id: string, humanDraft: string): Promise<EmailSession> {
    return request<EmailSession>(`/drafts/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ human_draft: humanDraft }),
    });
  },

  /** Approve and send the draft via Gmail. */
  approveDraft(id: string): Promise<ApproveResponse> {
    return request<ApproveResponse>(`/drafts/${id}/approve`, {
      method: "POST",
    });
  },

  /** Discard the draft (marks as discarded in DB). */
  discardDraft(id: string): Promise<DiscardResponse> {
    return request<DiscardResponse>(`/drafts/${id}`, {
      method: "DELETE",
    });
  },
};
