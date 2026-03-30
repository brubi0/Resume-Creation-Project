import { useState, useEffect, useCallback } from "react";
import api from "../api";
import { useAuth } from "../auth-context";
import CandidateList from "../components/CandidateList";
import CreateCandidateModal from "../components/CreateCandidateModal";
import GenerateProfileModal from "../components/GenerateProfileModal";
import TargetingModal from "../components/TargetingModal";

interface Candidate {
  id: string;
  name: string;
  username: string;
  created_at: string;
  session_id: string | null;
  session_status: string | null;
  session_phase: number | null;
}

export default function AdminDashboard() {
  const { logout } = useAuth();
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [showGenerateProfile, setShowGenerateProfile] = useState(false);
  const [targetingCandidate, setTargetingCandidate] = useState<Candidate | null>(null);
  const [profileBanner, setProfileBanner] = useState<string | null>(null);
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

  const handleGenerate = async (sessionId: string) => {
    try {
      await api.post(`/deliverables/generate?session_id=${sessionId}`);
      loadCandidates();
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
              onClick={() => setShowGenerateProfile(true)}
              className="rounded-lg border border-brand-dark px-4 py-2 text-sm font-medium text-brand-dark hover:bg-brand-dark/5"
            >
              + Generate Profile
            </button>
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
        {profileBanner && (
          <div className="mb-4 flex items-center justify-between rounded-lg border border-brand-green/40 bg-brand-green/10 px-4 py-3">
            <p className="text-sm text-brand-dark">{profileBanner}</p>
            <button
              onClick={() => setProfileBanner(null)}
              className="ml-4 text-xs text-gray-400 hover:text-gray-600"
            >
              Dismiss
            </button>
          </div>
        )}
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
              onTarget={setTargetingCandidate}
            />
          )}
        </div>
      </main>

      {showGenerateProfile && (
        <GenerateProfileModal
          onCreated={(profile) => {
            setShowGenerateProfile(false);
            setProfileBanner(
              `Profile "${profile.name}" generated and saved — candidates can now select it.`
            );
          }}
          onClose={() => setShowGenerateProfile(false)}
        />
      )}

      {showCreate && (
        <CreateCandidateModal
          onCreated={() => {
            setShowCreate(false);
            loadCandidates();
          }}
          onClose={() => setShowCreate(false)}
        />
      )}

      {targetingCandidate && (
        <TargetingModal
          sessionId={targetingCandidate.session_id!}
          candidateName={targetingCandidate.name}
          onDone={() => {
            setTargetingCandidate(null);
            setProfileBanner(`Targeted resume generated for ${targetingCandidate.name}.`);
          }}
          onClose={() => setTargetingCandidate(null)}
        />
      )}
    </div>
  );
}
