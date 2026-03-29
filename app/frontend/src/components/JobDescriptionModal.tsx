import { useState } from "react";

interface Props {
  initialValue?: string;
  onSave: (jd: string) => void;
  onSkip: () => void;
  saveLabel?: string;
}

export default function JobDescriptionModal({
  initialValue = "",
  onSave,
  onSkip,
  saveLabel = "Save & Start Interview",
}: Props) {
  const [jd, setJd] = useState(initialValue);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl">
        <h2 className="mb-1 text-lg font-bold text-brand-dark">
          Target Job Description
        </h2>
        <p className="mb-4 text-sm text-gray-500">
          Paste a job posting and the interview will be tailored to match it.
          You can also skip this and add one later.
        </p>

        <textarea
          value={jd}
          onChange={(e) => setJd(e.target.value)}
          placeholder="Paste the full job description here..."
          className="h-64 w-full resize-none rounded-lg border border-gray-300 p-3 text-sm focus:border-brand-dark focus:outline-none focus:ring-1 focus:ring-brand-dark"
        />

        <div className="mt-4 flex items-center justify-end gap-3">
          <button
            onClick={onSkip}
            className="rounded-lg px-4 py-2 text-sm text-gray-500 hover:text-gray-700"
          >
            Skip for now
          </button>
          <button
            onClick={() => onSave(jd)}
            disabled={!jd.trim()}
            className="rounded-lg bg-brand-dark px-4 py-2 text-sm font-medium text-white hover:bg-opacity-90 disabled:opacity-40"
          >
            {saveLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
