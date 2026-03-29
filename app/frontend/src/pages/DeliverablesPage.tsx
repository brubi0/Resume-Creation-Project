import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth-context";
import DeliverableCard from "../components/DeliverableCard";

interface Deliverable {
  id: string;
  type: string;
  filename: string;
  created_at: string;
}

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

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-brand-dark">
              Your Deliverables
            </h1>
            <p className="text-xs text-gray-500">
              Download your resume and supporting documents
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
        ) : deliverables.length === 0 ? (
          <div className="py-12 text-center">
            <p className="text-gray-400">
              No deliverables yet. Complete the interview first.
            </p>
          </div>
        ) : (
          <div className="grid gap-3">
            {deliverables.map((d) => (
              <DeliverableCard
                key={d.id}
                id={d.id}
                type={d.type}
                filename={d.filename}
                created_at={d.created_at}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
