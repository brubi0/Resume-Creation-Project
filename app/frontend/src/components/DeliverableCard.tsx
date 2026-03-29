import api from "../api";

interface Props {
  id: string;
  type: string;
  filename: string;
  created_at: string;
}

const TYPE_LABELS: Record<string, string> = {
  resume_md: "Resume (Markdown)",
  resume_docx: "Resume (Word)",
  interview_prep_md: "Interview Prep",
  skills_matrix_html: "Skills Matrix",
  score_card_md: "Score Card",
  cover_letter_md: "Cover Letter (Markdown)",
  cover_letter_docx: "Cover Letter (Word)",
  linkedin_guide_md: "LinkedIn Guide",
};

const TYPE_ICONS: Record<string, string> = {
  resume_docx: "W",
  resume_md: "M",
  interview_prep_md: "I",
  skills_matrix_html: "H",
  score_card_md: "S",
};

export default function DeliverableCard({
  id,
  type,
  filename,
  created_at,
}: Props) {
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

  return (
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
      <button
        onClick={handleDownload}
        className="rounded-lg bg-brand-dark px-3 py-1.5 text-xs font-medium text-white hover:bg-opacity-90"
      >
        Download
      </button>
    </div>
  );
}
