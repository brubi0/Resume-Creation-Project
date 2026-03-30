import { useState } from "react";
import api from "../api";

interface GeneratedProfile {
  slug: string;
  name: string;
  industry: string;
  target_roles: string;
}

interface Props {
  onCreated: (profile: GeneratedProfile) => void;
  onClose: () => void;
}

export default function GenerateProfileModal({ onCreated, onClose }: Props) {
  const [roleName, setRoleName] = useState("");
  const [industry, setIndustry] = useState("");
  const [tools, setTools] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!roleName.trim()) return;
    setGenerating(true);
    setError(null);
    try {
      const res = await api.post("/admin/profiles/generate", {
        role_name: roleName.trim(),
        industry: industry.trim(),
        must_have_tools: tools.trim(),
      });
      onCreated(res.data);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Generation failed. Try again.";
      setError(msg);
      setGenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
        <h2 className="mb-1 text-lg font-bold text-brand-dark">
          Generate New Profile
        </h2>
        <p className="mb-5 text-sm text-gray-500">
          Claude will search for current job postings and build a skills profile
          for the target role. This takes 30–60 seconds.
        </p>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">
              Target Role <span className="text-brand-coral">*</span>
            </label>
            <input
              type="text"
              value={roleName}
              onChange={(e) => setRoleName(e.target.value)}
              placeholder="e.g. Senior Software Engineer"
              disabled={generating}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-dark focus:outline-none focus:ring-1 focus:ring-brand-dark disabled:bg-gray-50"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">
              Industry{" "}
              <span className="font-normal text-gray-400">(optional)</span>
            </label>
            <input
              type="text"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              placeholder="e.g. SaaS / B2B Technology"
              disabled={generating}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-dark focus:outline-none focus:ring-1 focus:ring-brand-dark disabled:bg-gray-50"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">
              Must-have tools / certs{" "}
              <span className="font-normal text-gray-400">(optional)</span>
            </label>
            <input
              type="text"
              value={tools}
              onChange={(e) => setTools(e.target.value)}
              placeholder="e.g. React, TypeScript, AWS"
              disabled={generating}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-dark focus:outline-none focus:ring-1 focus:ring-brand-dark disabled:bg-gray-50"
            />
          </div>
        </div>

        {generating && (
          <div className="mt-5 flex items-center gap-3 rounded-lg bg-gray-50 px-4 py-3">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-brand-dark border-t-transparent" />
            <p className="text-sm text-gray-600">
              Searching job postings and building profile…
            </p>
          </div>
        )}

        {error && (
          <p className="mt-4 text-sm text-red-500">{error}</p>
        )}

        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            disabled={generating}
            className="rounded-lg px-4 py-2 text-sm text-gray-500 hover:text-gray-700 disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            onClick={handleGenerate}
            disabled={!roleName.trim() || generating}
            className="rounded-lg bg-brand-dark px-4 py-2 text-sm font-medium text-white hover:bg-opacity-90 disabled:opacity-40"
          >
            {generating ? "Generating…" : "Generate Profile"}
          </button>
        </div>
      </div>
    </div>
  );
}
