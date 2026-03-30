import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth-context";
import DeliverableCard from "../components/DeliverableCard";

interface Deliverable {
  id: string;
  session_id: string;
  type: string;
  filename: string;
  created_at: string;
  candidate_name: string;
  target_role: string;
}

type GroupKey = string; // "Candidate Name — Target Role" or just "Target Role"

export default function DeliverablesPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [deliverables, setDeliverables] = useState<Deliverable[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get("/deliverables")
      .then((res) => setDeliverables(res.data))
      .finally(() => setLoading(false));
  }, []);

  // Targeted deliverable types
  const TARGETED_TYPES = new Set(["resume_targeted_md", "resume_targeted_docx", "cover_letter_md", "cover_letter_docx"]);

  // Extract company from targeted filename e.g. "Bruno_Rubio_Resume_Acme_Corp_NetSuite.md"
  function targetLabel(d: Deliverable): string {
    const match = d.filename.match(/Resume_(.+?)\.(md|docx)$/) ?? d.filename.match(/Cover_Letter_(.+?)\.(md|docx)$/);
    return match?.[1]?.replace(/_/g, " ") ?? "Targeted";
  }

  // Build ordered groups: key → deliverables[]
  const groups = deliverables.reduce<Map<GroupKey, Deliverable[]>>((acc, d) => {
    const baseKey =
      user?.role === "admin"
        ? `${d.candidate_name} — ${d.target_role}`
        : d.target_role;
    const key = TARGETED_TYPES.has(d.type) ? `${baseKey} → ${targetLabel(d)}` : baseKey;
    if (!acc.has(key)) acc.set(key, []);
    acc.get(key)!.push(d);
    return acc;
  }, new Map());

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-brand-dark">
              {user?.role === "admin" ? "All Deliverables" : "Your Deliverables"}
            </h1>
            <p className="text-xs text-gray-500">
              Download resumes and supporting documents
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() =>
                navigate(user?.role === "admin" ? "/admin" : "/chat")
              }
              className="text-sm text-brand-dark hover:underline"
            >
              Back
            </button>
            <button
              onClick={logout}
              className="text-sm text-gray-500 hover:text-brand-coral"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-6">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-brand-dark border-t-transparent" />
          </div>
        ) : groups.size === 0 ? (
          <div className="py-12 text-center">
            <p className="text-gray-400">
              No deliverables yet. Complete the interview first.
            </p>
          </div>
        ) : (
          <div className="space-y-8">
            {Array.from(groups.entries()).map(([groupKey, items]) => (
              <section key={groupKey}>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
                  {groupKey}
                </h2>
                <div className="grid gap-3">
                  {items.map((d) => (
                    <DeliverableCard
                      key={d.id}
                      id={d.id}
                      type={d.type}
                      filename={d.filename}
                      created_at={d.created_at}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
