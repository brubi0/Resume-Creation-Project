import { useState, useEffect, useCallback } from "react";
import api from "../api";
import { useAuth } from "../auth-context";
import CandidateList from "../components/CandidateList";
import CreateCandidateModal from "../components/CreateCandidateModal";

interface Candidate {
  id: string;
  name: string;
  username: string;
  created_at: string;
  session_status: string | null;
  session_phase: number | null;
}

export default function AdminDashboard() {
  const { logout } = useAuth();
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadCandidates = useCallback(async () => {
    try {
      const res = await api.get("/admin/candidates");
      setCandidates(res.data);
    } catch {
      // handled by interceptor
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this candidate and all their data?")) return;
    await api.delete(`/admin/candidates/${id}`);
    loadCandidates();
  };

  const handleGenerate = async (candidateId: string) => {
    // Find the candidate's session by looking at their data
    // For now, we'll use a dedicated admin endpoint
    try {
      // Get the candidate's sessions to find the active one
      const sessionsRes = await api.get(`/admin/candidates`);
      const candidate = sessionsRes.data.find(
        (c: Candidate) => c.id === candidateId,
      );
      if (candidate?.session_status === "interview_complete") {
        // We need the session ID — for MVP, trigger via the admin candidates list
        alert(
          "Deliverable generation will be available when the session endpoint is ready.",
        );
      }
    } catch {
      alert("Failed to trigger generation");
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-brand-dark">
              Resume Chat Admin
            </h1>
            <p className="text-xs text-gray-500">
              Manage candidates and sessions
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowCreate(true)}
              className="rounded-lg bg-brand-dark px-4 py-2 text-sm font-medium text-white hover:bg-opacity-90"
            >
              + New Candidate
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

      <main className="mx-auto max-w-5xl px-6 py-6">
        {/* Stats */}
        <div className="mb-6 grid grid-cols-3 gap-4">
          <div className="rounded-xl bg-white p-4 shadow-sm">
            <p className="text-2xl font-bold text-brand-dark">
              {candidates.length}
            </p>
            <p className="text-xs text-gray-500">Total Candidates</p>
          </div>
          <div className="rounded-xl bg-white p-4 shadow-sm">
            <p className="text-2xl font-bold text-brand-green">
              {candidates.filter((c) => c.session_status === "active").length}
            </p>
            <p className="text-xs text-gray-500">Active Interviews</p>
          </div>
          <div className="rounded-xl bg-white p-4 shadow-sm">
            <p className="text-2xl font-bold text-brand-gold">
              {
                candidates.filter(
                  (c) => c.session_status === "deliverables_generated",
                ).length
              }
            </p>
            <p className="text-xs text-gray-500">Completed</p>
          </div>
        </div>

        {/* Candidate list */}
        <div className="rounded-xl bg-white shadow-sm">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-6 w-6 animate-spin rounded-full border-4 border-brand-dark border-t-transparent" />
            </div>
          ) : (
            <CandidateList
              candidates={candidates}
              onDelete={handleDelete}
              onGenerateDeliverables={handleGenerate}
            />
          )}
        </div>
      </main>

      {showCreate && (
        <CreateCandidateModal
          onCreated={() => {
            setShowCreate(false);
            loadCandidates();
          }}
          onClose={() => setShowCreate(false)}
        />
      )}
    </div>
  );
}
