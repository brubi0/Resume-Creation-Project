import ReactMarkdown from "react-markdown";

interface Props {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export default function ChatMessage({ role, content, timestamp }: Props) {
  const isUser = role === "user";
  const time = new Date(timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? "rounded-br-md bg-brand-dark text-white"
            : "rounded-bl-md bg-white text-gray-800 shadow-sm border border-gray-100"
        }`}
      >
        <div className={`prose prose-sm max-w-none ${isUser ? "prose-invert" : ""}`}>
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>
        <p
          className={`mt-1 text-[10px] ${isUser ? "text-white/60" : "text-gray-400"}`}
        >
          {time}
        </p>
      </div>
    </div>
  );
}
