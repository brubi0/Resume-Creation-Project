import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth-context";
import PhaseIndicator from "../components/PhaseIndicator";
import ChatMessage from "../components/ChatMessage";
import ChatInput from "../components/ChatInput";

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
  status: string;
}

export default function CandidateChat() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [sending, setSending] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

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
          status: sessionRes.data.status,
        });
        setMessages(messagesRes.data);

        // If no messages yet and session is active, send an initial greeting to kick off the interview
        if (messagesRes.data.length === 0 && sessionRes.data.status === "active") {
          setSending(true);
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
          // Refresh status after first exchange
          const statusRes = await api.get("/chat/status");
          setStatus(statusRes.data);
          setSending(false);
        }
        // If session is complete with no messages, go straight to deliverables
        if (
          messagesRes.data.length === 0 &&
          ["complete", "deliverables_generated"].includes(sessionRes.data.status)
        ) {
          navigate("/deliverables");
          return;
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

  const handleSend = async (content: string) => {
    // Optimistic user message
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

      // Refresh status for phase changes
      const statusRes = await api.get("/chat/status");
      setStatus(statusRes.data);
    } catch {
      setMessages((prev) =>
        prev.filter((m) => m.id !== tempMsg.id),
      );
    } finally {
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
      {/* Header */}
      <header className="flex items-center justify-between border-b bg-white px-4 py-3 shadow-sm">
        <div>
          <h1 className="text-lg font-semibold text-brand-dark">
            Resume Chat
          </h1>
          <p className="text-xs text-gray-500">Welcome, {user?.name}</p>
        </div>
        <div className="flex items-center gap-3">
          {status?.status === "interview_complete" ||
          status?.status === "deliverables_generated" ||
          status?.status === "complete" ? (
            <button
              onClick={() => navigate("/deliverables")}
              className="rounded-lg bg-brand-green px-3 py-1.5 text-xs font-medium text-white"
            >
              View Deliverables
            </button>
          ) : null}
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

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput onSend={handleSend} disabled={sending} />
    </div>
  );
}
