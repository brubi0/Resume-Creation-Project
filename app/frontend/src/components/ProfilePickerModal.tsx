import { useEffect, useState } from "react";
import api from "../api";

interface Profile {
  slug: string;
  name: string;
  industry: string;
  target_roles: string;
}

interface Props {
  onSelect: (slug: string) => void;
  onSkip: () => void;
}

export default function ProfilePickerModal({ onSelect, onSkip }: Props) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .get("/chat/profiles")
      .then((res) => setProfiles(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleConfirm = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      await api.patch("/chat/profile", { profile_slug: selected });
      onSelect(selected);
    } catch {
      // fall through to skip if it fails
      onSkip();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl">
        <div className="border-b px-6 py-5">
          <h2 className="text-lg font-bold text-brand-dark">
            What role are you targeting?
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Choose the closest match — or skip and describe your role in the
            chat.
          </p>
        </div>

        <div className="max-h-80 overflow-y-auto px-6 py-4">
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-4 border-brand-dark border-t-transparent" />
            </div>
          ) : profiles.length === 0 ? (
            <p className="py-6 text-center text-sm text-gray-400">
              No profiles available — your interviewer will help identify your
              role.
            </p>
          ) : (
            <div className="space-y-2">
              {profiles.map((p) => (
                <button
                  key={p.slug}
                  onClick={() =>
                    setSelected(selected === p.slug ? null : p.slug)
                  }
                  className={`w-full rounded-xl border px-4 py-3 text-left transition-colors ${
                    selected === p.slug
                      ? "border-brand-dark bg-brand-dark/5"
                      : "border-gray-200 hover:border-brand-dark/40 hover:bg-gray-50"
                  }`}
                >
                  <p className="font-medium text-brand-dark">{p.name}</p>
                  {p.industry && (
                    <p className="mt-0.5 text-xs text-gray-500">{p.industry}</p>
                  )}
                  {p.target_roles && (
                    <p className="mt-1 text-xs text-gray-400 line-clamp-1">
                      {p.target_roles}
                    </p>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 border-t px-6 py-4">
          <button
            onClick={onSkip}
            className="rounded-lg px-4 py-2 text-sm text-gray-500 hover:text-gray-700"
          >
            My role isn&apos;t listed
          </button>
          <button
            onClick={handleConfirm}
            disabled={!selected || saving}
            className="rounded-lg bg-brand-dark px-4 py-2 text-sm font-medium text-white hover:bg-opacity-90 disabled:opacity-40"
          >
            {saving ? "Saving…" : "Use This Profile"}
          </button>
        </div>
      </div>
    </div>
  );
}
