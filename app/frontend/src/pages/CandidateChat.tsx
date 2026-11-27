import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth-context";
import PhaseIndicator from "../components/PhaseIndicator";
import ChatMessage from "../components/ChatMessage";
import ChatInput from "../components/ChatInput";
import JobDescriptionModal from "../components/JobDescriptionModal";
import ProfilePickerModal from "../components/ProfilePickerModal";
import ResumeUploadModal from "../components/ResumeUploadModal";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  phase: number;
  created_at: string;
  status?: "ok" | "pending" | "failed";
  client_message_id?: string | null;
}

interface SessionStatus {
  phase: number;
  experience_level: string | null;
  profile_slug: string | null;
  job_description: string | null;
  status: string;
}

const KICKOFF_TEXT = "Hello, I'd like help with my resume.";
const POLL_MS = 3000;
const POLL_MAX = 20;

// crypto.randomUUID needs a secure context (https or localhost); fall back to a v4 otherwise.
function newId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

const COMPLETE_STATUSES = ["complete", "deliverables_generated", "interview_complete"];

export default function CandidateChat() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [sending, setSending] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [showResumeModal, setShowResumeModal] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showJdModal, setShowJdModal] = useState(false);
  const [showJdView, setShowJdView] = useState(false);
  const [newMsgId, setNewMsgId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [replaced, setReplaced] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const pollTimer = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimer.current !== null) {
      window.clearTimeout(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);
  useEffect(() => stopPolling, [stopPolling]);

  // Another request (a retry, a refresh mid-turn) holds the turn: refetch every 3 s,
  // at most POLL_MAX times, until the server says it is idle.
  const schedulePoll = useCallback(
    (attempt: number) => {
      stopPolling();
      if (attempt >= POLL_MAX) {
        setWaiting(false);
        setNotice("This is taking longer than expected. Refresh the page to check.");
        return;
      }
      setWaiting(true);
      setNotice("Still working on your last message…");
      pollTimer.current = window.setTimeout(async () => {
        pollTimer.current = null;
        try {
          const [m, s] = await Promise.all([
            api.get("/chat/messages"),
            api.get("/chat/session"),
          ]);
          const list: Message[] = m.data;
          const serverIds = new Set(list.map((x) => x.client_message_id).filter(Boolean));
          // Keep messages the server never stored (marked failed, Try again) at the end.
          setMessages((prev) => [
            ...list,
            ...prev.filter(
              (x) => x.id.startsWith("local-") && !(x.client_message_id && serverIds.has(x.client_message_id))
            ),
          ]);
          setSessionId(s.data.id);
          if (s.data.turn_state === "pending") {
            schedulePoll(attempt + 1);
            return;
          }
          const statusRes = await api.get("/chat/status");
          setStatus(statusRes.data);
          const last = list[list.length - 1];
          if (last && last.role === "assistant") setNewMsgId(last.id);
          setWaiting(false);
          setNotice(null);
        } catch {
          schedulePoll(attempt + 1);
        }
      }, POLL_MS);
    },
    [stopPolling]
  );

  const isComplete = COMPLETE_STATUSES.includes(status?.status ?? "");
  // "New session" = active with no messages yet, regardless of phase
  // (phase may be 1 if the candidate pre-selected a profile)
  const isNewSession =
    status?.status === "active" && messages.length === 0;

  // Load session and messages on mount
  useEffect(() => {
    const init = async () => {
      try {
        const [sessionRes, messagesRes] = await Promise.all([
          api.get("/chat/session"),
          api.get("/chat/messages"),
        ]);
        setStatus({
          phase: sessionRes.data.phase,
          experience_level: sessionRes.data.experience_level,
          profile_slug: sessionRes.data.profile_slug,
          job_description: sessionRes.data.job_description,
          status: sessionRes.data.status,
        });
        setMessages(messagesRes.data);
        setSessionId(sessionRes.data.id);

        // A reply may still be in flight (refresh mid-turn): wait for it.
        if (sessionRes.data.turn_state === "pending") schedulePoll(0);

        // New active session with no messages — run onboarding modals
        if (messagesRes.data.length === 0 && sessionRes.data.status === "active") {
          if (sessionRes.data.phase === 0) {
            // Full flow: resume → profile → JD → start
            setShowResumeModal(true);
          } else if (sessionRes.data.phase === 1) {
            // Profile already chosen (e.g. reloaded after picking profile) — go straight to JD
            setShowJdModal(true);
          }
        }
      } catch {
        // Session error handled by interceptor
      } finally {
        setInitializing(false);
      }
    };
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleResumeDone = () => {
    setShowResumeModal(false);
    setShowProfileModal(true);
  };

  const handleProfileDone = () => {
    setShowProfileModal(false);
    setShowJdModal(true);
  };

  // One send path for every turn (kickoff included). A retry passes the SAME
  // client_message_id, so the server reuses the saved message instead of duplicating it.
  const sendTurn = async (content: string, cmid: string) => {
    setSending(true);
    setNotice(null);
    setMessages((prev) =>
      prev.map((m) => (m.client_message_id === cmid ? { ...m, status: "pending" } : m))
    );
    const markFailed = () =>
      setMessages((prev) =>
        prev.map((m) => (m.client_message_id === cmid ? { ...m, status: "failed" } : m))
      );
    try {
      const res = await api.post("/chat/send", {
        content,
        session_id: sessionId ?? undefined,
        client_message_id: cmid,
      });
      setMessages((prev) => [
        ...prev.map((m) => (m.client_message_id === cmid ? { ...m, status: "ok" as const } : m)),
        res.data,
      ]);
      setNewMsgId(res.data.id);
      const statusRes = await api.get("/chat/status");
      setStatus(statusRes.data);
    } catch (err) {
      const e = err as { response?: { status?: number; data?: { code?: string } } };
      const code = e.response?.data?.code;
      if (e.response?.status === 409 && code === "session_replaced") {
        markFailed();
        setReplaced(true);
      } else if (e.response?.status === 409 && code === "turn_in_progress") {
        // The server may never have stored this message: keep it in the thread as
        // not sent (Try again resends the same client_message_id once the turn is free).
        markFailed();
        schedulePoll(0);
      } else {
        // network error, 503, 422 or anything else: the answer stays in the thread
        markFailed();
      }
    } finally {
      setSending(false);
    }
  };

  const addAndSend = (content: string) => {
    const cmid = newId();
    setMessages((prev) => [
      ...prev,
      {
        id: `local-${cmid}`,
        role: "user",
        content,
        phase: status?.phase ?? 0,
        created_at: new Date().toISOString(),
        status: "pending",
        client_message_id: cmid,
      },
    ]);
    return sendTurn(content, cmid);
  };

  const kickOffInterview = () => addAndSend(KICKOFF_TEXT);

  const handleJdSave = async (jd: string) => {
    try {
      const res = await api.patch("/chat/job-description", {
        job_description: jd,
      });
      setStatus((prev) =>
        prev ? { ...prev, job_description: res.data.job_description } : prev
      );
    } catch {
      // continue anyway
    }
    setShowJdModal(false);
    await kickOffInterview();
  };

  const handleJdUpdate = async (jd: string) => {
    try {
      const res = await api.patch("/chat/job-description", {
        job_description: jd,
      });
      setStatus((prev) =>
        prev ? { ...prev, job_description: res.data.job_description } : prev
      );
    } catch {
      // silent
    }
    setShowJdModal(false);
  };

  const handleJdSkip = async () => {
    setShowJdModal(false);
    await kickOffInterview();
  };

  const handleSend = (content: string) => addAndSend(content);

  const handleRetry = (msg: Message) => {
    if (msg.client_message_id) sendTurn(msg.content, msg.client_message_id);
  };

  const handleNewSession = async () => {
    setSending(true);
    try {
      await api.post("/chat/new-session", { replaces_session_id: sessionId });
      window.location.reload();
    } catch {
      setSending(false);
    }
  };

  if (initializing) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-ink border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-paper">
      {/* Resume Upload Modal — shown first for new sessions */}
      {showResumeModal && (
        <ResumeUploadModal onDone={handleResumeDone} />
      )}

      {/* Profile Picker — shown after resume upload for new sessions */}
      {showProfileModal && (
        <ProfilePickerModal
          onSelect={handleProfileDone}
          onSkip={handleProfileDone}
        />
      )}

      {/* JD Modal — shown for new sessions or mid-interview add/edit */}
      {showJdModal && (
        <JobDescriptionModal
          initialValue={status?.job_description ?? ""}
          onSave={isNewSession ? handleJdSave : handleJdUpdate}
          onSkip={isNewSession ? handleJdSkip : () => setShowJdModal(false)}
          saveLabel={isNewSession ? "Save and start interview" : "Save"}
          stepLabel={isNewSession ? "Step 3 of 3" : undefined}
        />
      )}

      {/* JD View panel */}
      {showJdView && status?.job_description && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-[2px]"
          onClick={() => setShowJdView(false)}
        >
          <div
            className="relative flex max-h-[80vh] w-full max-w-2xl flex-col rounded-xl bg-sheet shadow-[0_12px_40px_-12px_rgba(30,42,71,0.35)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-rule px-6 py-4">
              <h2 className="font-serif text-xl text-ink">Job posting</h2>
              <button
                onClick={() => setShowJdView(false)}
                className="rounded-lg px-3 py-1 text-sm text-slate hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
              >
                Close
              </button>
            </div>
            <div className="flex-1 overflow-y-auto whitespace-pre-wrap px-6 py-4 text-[15px] text-slate">
              {status.job_description}
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="flex items-center justify-between border-b border-rule bg-sheet px-4 py-3">
        <div>
          <h1 className="font-serif text-xl leading-tight text-ink">Resume Chat</h1>
          <p className="hidden text-xs text-slate sm:block">{user?.name}</p>
        </div>
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Job posting buttons: View (completed), Add/Edit (active) */}
          {status?.job_description && isComplete && (
            <button
              onClick={() => setShowJdView(true)}
              className="rounded-lg px-2.5 py-1.5 text-sm font-medium sm:px-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink border border-rule text-ink hover:border-ink"
            >
              View job posting
            </button>
          )}
          {!isNewSession && !isComplete && (
            <button
              onClick={() => setShowJdModal(true)}
              className="rounded-lg px-2.5 py-1.5 text-sm font-medium sm:px-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink border border-rule text-ink hover:border-ink"
            >
              {status?.job_description ? "Edit job posting" : "Add job posting"}
            </button>
          )}
          {isComplete && (
            <button
              onClick={() => navigate("/deliverables")}
              className="rounded-lg px-2.5 py-1.5 text-sm font-medium sm:px-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink bg-ink text-white hover:bg-ink/90"
            >
              Your documents
            </button>
          )}
          <button
            onClick={logout}
            className="rounded-lg px-1.5 py-1.5 text-sm text-slate hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            Sign out
          </button>
        </div>
      </header>

      {/* Phase indicator */}
      <PhaseIndicator currentPhase={status?.phase ?? 0} />

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 && isComplete ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <p className="mb-2 font-serif text-2xl text-ink">
              Your interview is complete
            </p>
            <p className="mb-5 text-[15px] text-slate">
              Your resume and supporting documents are ready.
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate("/deliverables")}
                className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:bg-ink/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
              >
                Your documents
              </button>
              <button
                onClick={handleNewSession}
                className="rounded-lg border border-rule px-4 py-2 text-sm font-medium text-ink hover:border-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
              >
                Start a new interview
              </button>
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <ChatMessage
                key={msg.id}
                role={msg.role}
                content={msg.content}
                timestamp={msg.created_at}
                isNew={msg.id === newMsgId}
                status={msg.status}
                onRetry={
                  msg.status === "failed" && i === messages.length - 1 && !replaced
                    ? () => handleRetry(msg)
                    : undefined
                }
                retryDisabled={sending || waiting}
              />
            ))}

            {notice && !replaced && (
              <div className="mx-auto mb-7 max-w-[68ch]" role="status">
                <p className="font-serif text-[15px] italic text-slate">{notice}</p>
              </div>
            )}

            {replaced && (
              <div
                className="mx-auto mb-7 flex max-w-[68ch] flex-wrap items-center gap-3 rounded-lg border border-rule bg-sheet px-4 py-3"
                role="alert"
              >
                <p className="flex-1 text-[15px] text-ink">
                  This interview was replaced in another tab.
                </p>
                <button
                  onClick={() => window.location.reload()}
                  className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:bg-ink/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
                >
                  Reload
                </button>
              </div>
            )}

            {sending && (
              <div className="mx-auto mb-7 max-w-[68ch]">
                <p className="animate-pulse font-serif text-[17px] italic text-slate">
                  Your interviewer is writing…
                </p>
              </div>
            )}
          </>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input — hide for completed sessions */}
      {!isComplete && !isNewSession && !replaced && (
        <ChatInput onSend={handleSend} disabled={sending || waiting} />
      )}
    </div>
  );
}
