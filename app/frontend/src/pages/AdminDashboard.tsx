import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
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
  completed_sets: number;
  generation_status: "idle" | "running" | "failed" | "done";
  generation_error: string | null;
  generation_kind?: "base" | "targeted" | null;
  generation_posting_id?: string | null;
}

export default function AdminDashboard() {
  const { logout } = useAuth();
  const navigate = useNavigate();
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

  const anyRunning = candidates.some((c) => c.generation_status === "running");
  useEffect(() => {
    if (!anyRunning) return;
    const t = setInterval(loadCandidates, 5000);
    return () => clearInterval(t);
  }, [anyRunning, loadCandidates]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this candidate and all their data?")) return;
    await api.delete(`/admin/candidates/${id}`);
    loadCandidates();
  };

  const handleGenerate = async (sessionId: string) => {
    try {
      await api.post(`/deliverables/generate?session_id=${sessionId}`);
      loadCandidates();
    } catch (err: any) {
      if (err?.response?.status === 409) {
        loadCandidates();
        return;
      }
      alert("Failed to trigger generation");
    }
  };

  const handleRetryTargeted = async (postingId: string) => {
    try {
      await api.post(`/deliverables/target/${postingId}/retry`);
      loadCandidates();
    } catch (err: any) {
      if (err?.response?.status === 409) {
        loadCandidates();
        return;
      }
      alert("Failed to trigger generation");
    }
  };

  const nActive = candidates.filter((c) => c.session_status === "active").length;
  const nReady = candidates.filter(
    (c) => c.session_status === "interview_complete",
  ).length;
  const nDone = candidates.filter(
    (c) => c.session_status === "deliverables_generated",
  ).length;
  const nNotStarted = candidates.filter((c) => !c.session_status).length;
  const num = "font-sans font-semibold tabular-nums";

  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-rule bg-sheet px-4 py-3 sm:px-6">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="font-serif text-xl leading-tight text-ink">Resume Chat</h1>
            <p className="text-xs text-slate">Admin</p>
          </div>
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <button
              onClick={() => navigate("/deliverables")}
              className="rounded-lg border border-rule px-3 py-2 text-sm font-medium text-ink hover:border-ink sm:px-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              All documents
            </button>
            <button
              onClick={() => setShowGenerateProfile(true)}
              className="rounded-lg border border-rule px-3 py-2 text-sm font-medium text-ink hover:border-ink sm:px-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              Generate profile
            </button>
            <button
              onClick={() => setShowCreate(true)}
              className="rounded-lg bg-ink px-3 py-2 text-sm font-medium text-white hover:bg-ink/90 sm:px-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              New candidate
            </button>
            <button
              onClick={logout}
              className="rounded-lg px-1.5 py-1.5 text-sm text-slate hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
        {profileBanner && (
          <div className="mb-4 flex items-center justify-between gap-2 rounded-lg border border-l-[3px] border-rule border-l-done bg-sheet px-4 py-3">
            <p className="min-w-0 break-words text-[15px] text-ink">{profileBanner}</p>
            <button
              onClick={() => setProfileBanner(null)}
              className="ml-4 rounded text-sm text-slate hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              Dismiss
            </button>
          </div>
        )}

        <h2 className="font-serif text-2xl text-ink">Candidates</h2>
        <p className="mb-6 mt-1 font-serif text-[17px] text-slate">
          <span className={`${num} text-ink`}>{candidates.length}</span>{" "}
          {candidates.length === 1 ? "candidate" : "candidates"}:{" "}
          <span className={`${num} text-ink`}>{nActive}</span> interviewing,{" "}
          <span className={`${num} text-ink`}>{nReady}</span> ready for documents,{" "}
          <span className={`${num} text-ink`}>{nDone}</span> complete
          {nNotStarted > 0 && (
            <>
              , <span className={`${num} text-ink`}>{nNotStarted}</span> not started
            </>
          )}
          .
        </p>

        {/* Candidate list */}
        <div className="rounded-xl border border-rule bg-sheet">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-6 w-6 animate-spin rounded-full border-4 border-ink border-t-transparent" />
            </div>
          ) : (
            <CandidateList
              candidates={candidates}
              onDelete={handleDelete}
              onGenerateDeliverables={handleGenerate}
              onRetryTargeted={handleRetryTargeted}
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
            setProfileBanner(`Tailored resume started for ${targetingCandidate.name}. It will appear under Documents shortly.`);
          }}
          onClose={() => setTargetingCandidate(null)}
        />
      )}
    </div>
  );
}
