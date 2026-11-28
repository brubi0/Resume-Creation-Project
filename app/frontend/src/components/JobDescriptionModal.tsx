import { useState } from "react";

interface Props {
  initialValue?: string;
  onSave: (jd: string) => void;
  onSkip: () => void;
  saveLabel?: string;
  stepLabel?: string;
}

export default function JobDescriptionModal({
  initialValue = "",
  onSave,
  onSkip,
  saveLabel = "Save and start interview",
  stepLabel,
}: Props) {
  const [jd, setJd] = useState(initialValue);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-[2px]">
      <div className="w-full max-w-2xl rounded-xl bg-sheet p-6 shadow-[0_12px_40px_-12px_rgba(30,42,71,0.35)]">
        {stepLabel && <p className="mb-1 text-xs text-slate">{stepLabel}</p>}
        <h2 className="mb-1 font-serif text-xl text-ink">Job posting</h2>
        <p className="mb-4 text-[15px] text-slate">
          Paste a job posting and the interview will be tailored to match it.
          You can also skip this and add one later.
        </p>

        <textarea
          value={jd}
          onChange={(e) => setJd(e.target.value)}
          placeholder="Paste the full job posting here"
          maxLength={20000}
          className="h-64 w-full resize-none rounded-lg border border-rule bg-sheet p-3 text-[15px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        />

        <div className="mt-4 flex items-center justify-end gap-3">
          <button
            onClick={onSkip}
            className="rounded-lg px-4 py-2 text-sm text-slate hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            Skip for now
          </button>
          <button
            onClick={() => onSave(jd)}
            disabled={!jd.trim()}
            className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:bg-ink/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:opacity-40"
          >
            {saveLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
