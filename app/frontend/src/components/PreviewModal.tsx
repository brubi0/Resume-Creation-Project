import { useEffect } from "react";
import ReactMarkdown from "react-markdown";

interface Props {
  content: string;
  contentType: string;
  filename: string;
  onClose: () => void;
}

function friendlyTitle(filename: string): string {
  return filename.replace(/\.[A-Za-z0-9]+$/, "").replace(/_/g, " ");
}

export default function PreviewModal({
  content,
  contentType,
  filename,
  onClose,
}: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="relative flex max-h-[90vh] w-full max-w-4xl flex-col rounded-xl bg-sheet shadow-[0_12px_40px_-12px_rgba(30,42,71,0.35)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-rule px-6 py-4">
          <h2 className="font-serif text-xl text-ink">{friendlyTitle(filename)}</h2>
          <button
            onClick={onClose}
            className="rounded-lg px-3 py-1 text-sm text-slate hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            Close
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto rounded-b-xl bg-paper px-3 py-6 sm:px-6">
          <div className="mx-auto max-w-[72ch] rounded-md border border-rule bg-sheet px-5 py-8 font-serif sm:px-10 sm:py-10">
            {contentType === "text/html" ? (
              <iframe
                sandbox=""
                srcDoc={content}
                title={`${friendlyTitle(filename)} preview`}
                className="block h-[70vh] min-h-[70vh] w-full border-0 bg-white"
              />
            ) : (
              <div className="md">
                <ReactMarkdown
                  components={{ a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}
                >{content}</ReactMarkdown>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
