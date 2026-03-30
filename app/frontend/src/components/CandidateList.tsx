interface Candidate {
  id: string;
  name: string;
  username: string;
  created_at: string;
  session_id: string | null;
  session_status: string | null;
  session_phase: number | null;
  completed_sets: number;
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

export default function CandidateList({
  candidates,
  onDelete,
  onGenerateDeliverables,
  onTarget,
}: Props) {
  if (candidates.length === 0) {
    return (
      <p className="py-8 text-center text-gray-400">
        No candidates yet. Create one to get started.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b text-xs font-medium uppercase text-gray-500">
            <th className="px-4 py-3">Name</th>
            <th className="px-4 py-3">Username</th>
            <th className="px-4 py-3">Phase</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Created</th>
            <th className="px-4 py-3">Actions</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => (
            <tr key={c.id} className="border-b hover:bg-gray-50">
              <td className="px-4 py-3 font-medium">{c.name}</td>
              <td className="px-4 py-3 text-gray-500">{c.username}</td>
              <td className="px-4 py-3">
                {c.session_phase != null
                  ? PHASE_NAMES[c.session_phase] ?? `Phase ${c.session_phase}`
                  : "-"}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={c.session_status} />
                {c.completed_sets > 1 && (
                  <p className="mt-0.5 text-xs text-gray-400">
                    {c.completed_sets} resume sets
                  </p>
                )}
              </td>
              <td className="px-4 py-3 text-gray-500">
                {new Date(c.created_at).toLocaleDateString()}
              </td>
              <td className="px-4 py-3">
                <div className="flex gap-2">
                  {c.session_status === "interview_complete" && c.session_id && (
                    <button
                      onClick={() => onGenerateDeliverables(c.session_id!)}
                      className="rounded bg-brand-green px-2 py-1 text-xs text-white hover:bg-opacity-90"
                    >
                      Generate
                    </button>
                  )}
                  {c.session_status === "deliverables_generated" && c.session_id && (
                    <button
                      onClick={() => onTarget(c)}
                      className="rounded bg-brand-gold px-2 py-1 text-xs text-white hover:bg-opacity-90"
                    >
                      Target
                    </button>
                  )}
                  <button
                    onClick={() => onDelete(c.id)}
                    className="rounded bg-brand-coral px-2 py-1 text-xs text-white hover:bg-opacity-90"
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-gray-400">-</span>;

  const colors: Record<string, string> = {
    active: "bg-blue-100 text-blue-700",
    interview_complete: "bg-brand-gold/20 text-yellow-700",
    deliverables_generated: "bg-brand-green/20 text-green-700",
  };

  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] ?? "bg-gray-100 text-gray-600"}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
