import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth-context";
import PhaseIndicator from "../components/PhaseIndicator";
import ChatMessage from "../components/ChatMessage";
import ChatInput from "../components/ChatInput";
import JobDescriptionModal from "../components/JobDescriptionModal";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  phase: number;
  created_at: string;
}

interface SessionStatus {
  phase: number;
  experience_level: string | null;
  profile_slug: string | null;
  job_description: string | null;
  status: string;
}

const COMPLETE_STATUSES = ["complete", "deliverables_generated", "interview_complete"];

export default function CandidateChat() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [sending, setSending] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [showJdModal, setShowJdModal] = useState(false);
  const [showJdView, setShowJdView] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const isComplete = COMPLETE_STATUSES.includes(status?.status ?? "");
  const isNewSession =
    status?.status === "active" && status?.phase === 0 && messages.length === 0;

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

        // New active session with no messages — show JD modal before starting
        if (
          messagesRes.data.length === 0 &&
          sessionRes.data.status === "active" &&
          sessionRes.data.phase === 0
        ) {
          setShowJdModal(true);
        }
      } catch {
        // Session error handled by interceptor
      } finally {
        setInitializing(false);
      }
    };
    init();
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const kickOffInterview = async () => {
    setSending(true);
    try {
      const res = await api.post("/chat/send", {
        content: "Hello, I'd like help with my resume.",
      });
      setMessages([
        {
          id: "init-user",
          role: "user",
          content: "Hello, I'd like help with my resume.",
          phase: 0,
          created_at: new Date().toISOString(),
        },
        res.data,
      ]);
      const statusRes = await api.get("/chat/status");
      setStatus(statusRes.data);
    } catch {
      // handled by interceptor
    } finally {
      setSending(false);
    }
  };

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

  const handleSend = async (content: string) => {
    const tempMsg: Message = {
      id: `temp-${Date.now()}`,
      role: "user",
      content,
      phase: status?.phase ?? 0,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempMsg]);
    setSending(true);

    try {
      const res = await api.post("/chat/send", { content });
      setMessages((prev) => [...prev, res.data]);
      const statusRes = await api.get("/chat/status");
      setStatus(statusRes.data);
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== tempMsg.id));
    } finally {
      setSending(false);
    }
  };

  const handleNewSession = async () => {
    setSending(true);
    try {
      await api.post("/chat/new-session");
      window.location.reload();
    } catch {
      setSending(false);
    }
  };

  if (initializing) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-dark border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-gray-50">
      {/* JD Modal — shown for new sessions or mid-interview add/edit */}
      {showJdModal && (
        <JobDescriptionModal
          initialValue={status?.job_description ?? ""}
          onSave={isNewSession ? handleJdSave : handleJdUpdate}
          onSkip={isNewSession ? handleJdSkip : () => setShowJdModal(false)}
          saveLabel={isNewSession ? "Save & Start Interview" : "Save"}
        />
      )}

      {/* JD View panel */}
      {showJdView && status?.job_description && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setShowJdView(false)}
        >
          <div
            className="relative flex max-h-[80vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b px-6 py-4">
              <h2 className="text-sm font-semibold text-brand-dark">
                Target Job Description
              </h2>
              <button
                onClick={() => setShowJdView(false)}
                className="rounded-lg px-3 py-1 text-sm text-gray-500 hover:bg-gray-100"
              >
                Close
              </button>
            </div>
            <div className="flex-1 overflow-y-auto whitespace-pre-wrap px-6 py-4 text-sm text-gray-700">
              {status.job_description}
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="flex items-center justify-between border-b bg-white px-4 py-3 shadow-sm">
        <div>
          <h1 className="text-lg font-semibold text-brand-dark">Resume Chat</h1>
          <p className="text-xs text-gray-500">Welcome, {user?.name}</p>
        </div>
        <div className="flex items-center gap-3">
          {/* JD buttons: View (completed), Add/Edit (active) */}
          {status?.job_description && isComplete && (
            <button
              onClick={() => setShowJdView(true)}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
            >
              View JD
            </button>
          )}
          {!isNewSession && !isComplete && (
            <button
              onClick={
                status?.job_description
                  ? () => setShowJdModal(true)
                  : () => setShowJdModal(true)
              }
              className={
                status?.job_description
                  ? "rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
                  : "rounded-lg border border-dashed border-gray-400 px-3 py-1.5 text-xs font-medium text-gray-500 hover:border-brand-dark hover:text-brand-dark"
              }
            >
              {status?.job_description ? "View / Edit JD" : "+ Add JD"}
            </button>
          )}
          {isComplete && (
            <button
              onClick={() => navigate("/deliverables")}
              className="rounded-lg bg-brand-green px-3 py-1.5 text-xs font-medium text-white"
            >
              View Deliverables
            </button>
          )}
          <button
            onClick={logout}
            className="text-sm text-gray-500 hover:text-brand-coral"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Phase indicator */}
      <PhaseIndicator currentPhase={status?.phase ?? 0} />

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 && isComplete ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <p className="mb-2 text-lg font-semibold text-brand-dark">
              Your interview is complete!
            </p>
            <p className="mb-4 text-sm text-gray-500">
              Your resume and documents are ready for download.
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate("/deliverables")}
                className="rounded-lg bg-brand-green px-4 py-2 text-sm font-medium text-white"
              >
                View Deliverables
              </button>
              <button
                onClick={handleNewSession}
                className="rounded-lg border border-brand-dark px-4 py-2 text-sm font-medium text-brand-dark hover:bg-brand-dark/5"
              >
                Start New Interview
              </button>
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                role={msg.role}
                content={msg.content}
                timestamp={msg.created_at}
              />
            ))}

            {sending && (
              <div className="mb-3 flex justify-start">
                <div className="rounded-2xl rounded-bl-md border border-gray-100 bg-white px-4 py-3 shadow-sm">
                  <div className="flex gap-1">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:0.1s]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:0.2s]" />
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input — hide for completed sessions */}
      {!isComplete && !isNewSession && (
        <ChatInput onSend={handleSend} disabled={sending} />
      )}
    </div>
  );
}
