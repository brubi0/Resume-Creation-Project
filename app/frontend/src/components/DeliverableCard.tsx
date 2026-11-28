import { useState } from "react";
import api from "../api";
import PreviewModal from "./PreviewModal";

interface Props {
  id: string;
  type: string;
  filename: string;
  created_at: string;
}

const TYPE_LABELS: Record<string, string> = {
  resume: "Resume",
  resume_md: "Resume",
  resume_docx: "Resume",
  resume_targeted_md: "Tailored resume",
  resume_targeted_docx: "Tailored resume",
  interview_prep: "Interview prep",
  interview_prep_md: "Interview prep",
  skills_matrix: "Skills matrix",
  skills_matrix_html: "Skills matrix",
  score_card: "Score card",
  score_card_md: "Score card",
  cover_letter_md: "Cover letter",
  cover_letter_docx: "Cover letter",
};

function formatTag(type: string): string {
  if (type.startsWith("score_card")) return "Markdown";
  if (type.endsWith("_docx") || type === "resume" || type === "interview_prep")
    return "Word";
  if (type.endsWith("_md")) return "Markdown";
  if (type.endsWith("_html") || type === "skills_matrix") return "Web page";
  return "File";
}

// Files that can be previewed in-browser
const PREVIEWABLE = new Set(["resume_md", "skills_matrix", "score_card", "resume_targeted_md", "cover_letter_md", "skills_matrix_html", "score_card_md", "interview_prep_md"]);

export default function DeliverableCard({
  id,
  type,
  filename,
  created_at,
}: Props) {
  const [preview, setPreview] = useState<{
    content: string;
    content_type: string;
    filename: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);

  const handleDownload = async () => {
    const res = await api.get(`/deliverables/${id}/download`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleView = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/deliverables/${id}/preview`);
      setPreview(res.data);
    } catch {
      // fallback: download instead
      handleDownload();
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-4">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-ink">{TYPE_LABELS[type] ?? type}</p>
          <p className="flex gap-3 whitespace-nowrap text-[13px] text-slate">
            <span>{formatTag(type)}</span>
            <span className="text-slate/80">
              {new Date(created_at).toLocaleDateString()}
            </span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {PREVIEWABLE.has(type) && (
            <button
              onClick={handleView}
              disabled={loading}
              className="rounded-lg border border-rule px-3 py-1.5 text-sm font-medium text-ink hover:border-ink disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              {loading ? "Loading…" : "Preview"}
            </button>
          )}
          <button
            onClick={handleDownload}
            className="rounded-lg bg-ink px-3 py-1.5 text-sm font-medium text-white hover:bg-ink/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            Download
          </button>
        </div>
      {preview && (
        <PreviewModal
          content={preview.content}
          contentType={preview.content_type}
          filename={preview.filename}
          onClose={() => setPreview(null)}
        />
      )}
      </div>
    </>
  );
}
