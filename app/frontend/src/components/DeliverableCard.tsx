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
  resume: "Resume (Word)",
  resume_md: "Resume (Markdown)",
  resume_targeted_md: "Targeted Resume (Markdown)",
  resume_targeted_docx: "Targeted Resume (Word)",
  interview_prep: "Interview Prep (Word)",
  interview_prep_md: "Interview Prep (Markdown)",
  skills_matrix: "Skills Matrix",
  skills_matrix_html: "Skills Matrix",
  score_card: "Score Card",
  score_card_md: "Score Card",
  cover_letter_md: "Cover Letter (Markdown)",
  cover_letter_docx: "Cover Letter (Word)",
};

const TYPE_ICONS: Record<string, string> = {
  resume: "W",
  resume_md: "M",
  resume_targeted_md: "M",
  resume_targeted_docx: "W",
  interview_prep: "W",
  interview_prep_md: "M",
  skills_matrix: "H",
  skills_matrix_html: "H",
  score_card: "S",
  score_card_md: "S",
  cover_letter_md: "CL",
  cover_letter_docx: "CL",
};

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
      <div className="flex items-center gap-3 rounded-xl border bg-white p-4 shadow-sm transition hover:shadow-md">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-dark/10 text-sm font-bold text-brand-dark">
          {TYPE_ICONS[type] ?? "F"}
        </div>
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-800">
            {TYPE_LABELS[type] ?? type}
          </p>
          <p className="text-xs text-gray-400">
            {new Date(created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {PREVIEWABLE.has(type) && (
            <button
              onClick={handleView}
              disabled={loading}
              className="rounded-lg border border-brand-dark px-3 py-1.5 text-xs font-medium text-brand-dark hover:bg-brand-dark/5 disabled:opacity-50"
            >
              {loading ? "Loading..." : "View"}
            </button>
          )}
          <button
            onClick={handleDownload}
            className="rounded-lg bg-brand-dark px-3 py-1.5 text-xs font-medium text-white hover:bg-opacity-90"
          >
            Download
          </button>
        </div>
      </div>

      {preview && (
        <PreviewModal
          content={preview.content}
          contentType={preview.content_type}
          filename={preview.filename}
          onClose={() => setPreview(null)}
        />
      )}
    </>
  );
}
