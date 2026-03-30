import { useState } from "react";
import api from "../api";

interface Props {
  sessionId: string;
  candidateName: string;
  onDone: () => void;
  onClose: () => void;
}

export default function TargetingModal({ sessionId, candidateName, onDone, onClose }: Props) {
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [postingText, setPostingText] = useState("");
  const [includeCoverLetter, setIncludeCoverLetter] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!company.trim() || !role.trim() || !postingText.trim()) {
      setError("Company, role, and job posting are required.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await api.post("/deliverables/target", {
        session_id: sessionId,
        company: company.trim(),
        role: role.trim(),
        posting_text: postingText.trim(),
        include_cover_letter: includeCoverLetter,
      });
      onDone();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Targeting failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="relative flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b px-6 py-4">
          <div>
            <h2 className="text-sm font-semibold text-brand-dark">Target Job Posting</h2>
            <p className="text-xs text-gray-500">{candidateName}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg px-3 py-1 text-sm text-gray-500 hover:bg-gray-100"
          >
            Cancel
          </button>
        </div>

        <div className="flex-1 overflow-y-auto space-y-4 px-6 py-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-700">Company</label>
              <input
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Acme Corp"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-dark focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-700">Role</label>
              <input
                type="text"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="NetSuite Administrator"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-dark focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">
              Job Posting <span className="text-gray-400">(paste full text)</span>
            </label>
            <textarea
              value={postingText}
              onChange={(e) => setPostingText(e.target.value)}
              rows={12}
              placeholder="Paste the full job description here..."
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-dark focus:outline-none resize-none"
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={includeCoverLetter}
              onChange={(e) => setIncludeCoverLetter(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 accent-brand-dark"
            />
            <span className="text-sm text-gray-700">Also generate a cover letter</span>
          </label>

          {error && <p className="text-xs text-red-500">{error}</p>}
        </div>

        <div className="border-t px-6 py-4">
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="w-full rounded-lg bg-brand-dark py-2.5 text-sm font-medium text-white hover:bg-opacity-90 disabled:opacity-50"
          >
            {loading ? "Generating targeted resume…" : "Generate Targeted Resume"}
          </button>
        </div>
      </div>
    </div>
  );
}
