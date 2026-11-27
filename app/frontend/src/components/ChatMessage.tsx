import ReactMarkdown from "react-markdown";

interface Props {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  isNew?: boolean;
  /** "failed" marks a user message the server never answered. */
  status?: "ok" | "pending" | "failed";
  /** Present only on the last failed message: resends the same client_message_id. */
  onRetry?: () => void;
  retryDisabled?: boolean;
}

export default function ChatMessage({
  role,
  content,
  timestamp,
  isNew = false,
  status = "ok",
  onRetry,
  retryDisabled = false,
}: Props) {
  const isUser = role === "user";
  const time = new Date(timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="mx-auto mb-7 max-w-[68ch]">
      {isUser ? (
        <div className="ml-8 sm:ml-16">
          <div className="rounded-lg border border-l-[3px] border-rule border-l-ink bg-sheet px-4 py-3 font-sans text-[15px] leading-relaxed">
            <div className="md">
              <ReactMarkdown components={{ a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}>{content}</ReactMarkdown>
            </div>
          </div>
          {isUser && status === "failed" ? (
            <p className="mt-1.5 flex items-center justify-end gap-2 text-xs text-danger" role="status">
              <span>Not sent.</span>
              {onRetry && (
                <button
                  type="button"
                  onClick={onRetry}
                  disabled={retryDisabled}
                  className="rounded px-1.5 py-0.5 font-medium text-ink underline underline-offset-2 hover:text-ink/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:opacity-40"
                >
                  Try again
                </button>
              )}
            </p>
          ) : (
            <p className="mt-1.5 text-right text-xs text-slate">{time}</p>
          )}
        </div>
      ) : (
        <div>
          <div className="font-serif text-[17px] leading-relaxed text-ink">
            <div className={`md md-voice${isNew ? " is-new" : ""}`}>
              <ReactMarkdown components={{ a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}>{content}</ReactMarkdown>
            </div>
          </div>
          <p className="mt-1.5 text-xs text-slate">{time}</p>
        </div>
      )}
    </div>
  );
}
