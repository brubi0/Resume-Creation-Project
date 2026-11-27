import { useNavigate } from "react-router-dom";

interface Candidate {
  id: string;
  name: string;
  username: string;
  created_at: string;
  session_id: string | null;
  session_status: string | null;
  session_phase: number | null;
  completed_sets: number;
  generation_status: "idle" | "running" | "failed" | "done";
  generation_error: string | null;
}

const PHASE_NAMES = [
  "Profile",
  "Review",
  "Interview",
  "Resume",
  "Prep",
  "Skills",
  "Score",
];

interface Props {
  candidates: Candidate[];
  onDelete: (id: string) => void;
  onGenerateDeliverables: (id: string) => void;
  onTarget: (candidate: Candidate) => void;
}

const STATUS: Record<string, { label: string; dot: string }> = {
  active: { label: "Interviewing", dot: "bg-ink" },
  interview_complete: {
    label: "Ready for documents",
    dot: "bg-hl ring-2 ring-ink/20",
  },
  deliverables_generated: { label: "Documents ready", dot: "bg-done" },
};

const FOCUS =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";

export default function CandidateList({
  candidates,
  onDelete,
  onGenerateDeliverables,
  onTarget,
}: Props) {
  const navigate = useNavigate();
  if (candidates.length === 0) {
    return (
      <p className="py-8 text-center text-slate">
        No candidates yet. Create one to get started.
      </p>
    );
  }

  const phaseOf = (c: Candidate) => {
    if (!c.session_status) return "Not started";
    if (
      c.session_status === "deliverables_generated" ||
      (c.session_phase != null && c.session_phase >= PHASE_NAMES.length)
    )
      return "Done";
    return c.session_phase != null
      ? PHASE_NAMES[c.session_phase] ?? "Done"
      : "Not started";
  };

  const actions = (c: Candidate) => (
    <>
      {c.generation_status === "failed" &&
        c.session_id &&
        (c.session_status === "interview_complete" ||
          c.session_status === "deliverables_generated") && (
          <button
            onClick={() => onGenerateDeliverables(c.session_id!)}
            className={`rounded-lg bg-ink px-3 py-1.5 text-sm font-medium text-white hover:bg-ink/90 ${FOCUS}`}
          >
            Try again
          </button>
        )}
      {c.generation_status !== "running" &&
        c.generation_status !== "failed" &&
        c.session_status === "interview_complete" && c.session_id && (
        <button
          onClick={() => onGenerateDeliverables(c.session_id!)}
          className={`rounded-lg bg-ink px-3 py-1.5 text-sm font-medium text-white hover:bg-ink/90 ${FOCUS}`}
        >
          Generate documents
        </button>
      )}
      {c.session_status === "deliverables_generated" && c.session_id && (
        <button
          onClick={() => navigate("/deliverables")}
          className={`rounded-lg border border-rule px-3 py-1.5 text-sm font-medium text-ink hover:border-ink ${FOCUS}`}
        >
          Documents
        </button>
      )}
      {c.session_status === "deliverables_generated" &&
        c.session_id &&
        c.generation_status !== "running" && (
        <button
          onClick={() => onTarget(c)}
          className={`rounded-lg border border-rule px-3 py-1.5 text-sm font-medium text-ink hover:border-ink ${FOCUS}`}
        >
          Tailor to a job
        </button>
      )}
      <button
        onClick={() => onDelete(c.id)}
        aria-label={`Delete ${c.name}`}
        className={`rounded-lg px-2 py-1.5 text-sm text-danger hover:underline ${FOCUS}`}
      >
        Delete
      </button>
    </>
  );

  return (
    <>
      {/* Mobile: stacked rows */}
      <ul className="divide-y divide-rule sm:hidden">
        {candidates.map((c) => (
          <li key={c.id} className="min-w-0 px-4 py-4">
            <p className="break-words font-semibold text-ink">{c.name}</p>
            <p className="break-all text-sm text-slate">{c.username}</p>
            <div className="mt-2 text-[15px]">
              <StatusLabel status={c.session_status} />
              <GenerationNote c={c} />
              {c.completed_sets > 1 && (
                <p className="mt-0.5 text-xs text-slate">
                  {c.completed_sets} resume sets
                </p>
              )}
            </div>
            {c.session_status && (
              <p className="mt-1 text-sm text-slate">Phase: {phaseOf(c)}</p>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {actions(c)}
            </div>
          </li>
        ))}
      </ul>

      {/* Desktop: table */}
      <div className="hidden overflow-x-auto sm:block">
        <table className="w-full text-left text-[15px]">
          <thead>
            <tr className="border-b border-rule text-[13px] font-medium text-slate">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Username</th>
              <th className="px-4 py-3 font-medium">Phase</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Created</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((c) => (
              <tr key={c.id} className="border-b border-rule last:border-b-0">
                <td className="px-4 py-3 font-semibold text-ink">{c.name}</td>
                <td className="px-4 py-3 text-slate">{c.username}</td>
                <td className="px-4 py-3">{phaseOf(c)}</td>
                <td className="px-4 py-3">
                  <StatusLabel status={c.session_status} />
                  <GenerationNote c={c} />
                  {c.completed_sets > 1 && (
                    <p className="mt-0.5 text-xs text-slate">
                      {c.completed_sets} resume sets
                    </p>
                  )}
                </td>
                <td className="px-4 py-3 text-slate">
                  {new Date(c.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {actions(c)}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function StatusLabel({ status }: { status: string | null }) {
  if (!status)
    return (
      <span className="inline-flex items-center gap-2 text-slate">
        <span className="h-2 w-2 rounded-full bg-slate" aria-hidden="true" />
        Not started
      </span>
    );
  const s = STATUS[status] ?? {
    label: status.replace(/_/g, " "),
    dot: "bg-slate",
  };
  return (
    <span className="inline-flex items-center gap-2">
      <span className={`h-2 w-2 rounded-full ${s.dot}`} aria-hidden="true" />
      {s.label}
    </span>
  );
}

function GenerationNote({ c }: { c: Candidate }) {
  if (c.generation_status === "running")
    return (
      <p
        role="status"
        className="mt-1 inline-flex items-center gap-2 text-sm text-slate"
      >
        <span
          className="h-2 w-2 animate-pulse rounded-full bg-hl ring-2 ring-ink/20"
          aria-hidden="true"
        />
        Generating documents…
      </p>
    );
  if (c.generation_status === "failed")
    return (
      <p role="alert" className="mt-1 max-w-xs text-sm text-danger">
        {c.generation_error || "Document generation failed. Try again."}
      </p>
    );
  return null;
}
