import { useRef, useState } from "react";
import api from "../api";

interface Props {
  onDone: (uploaded: boolean) => void;
}

export default function ResumeUploadModal({ onDone }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setError(null);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      await api.post("/chat/resume", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      onDone(true);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Upload failed. Try a different file.";
      setError(msg);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
        <h2 className="mb-1 text-lg font-bold text-brand-dark">
          Upload Your Current Resume
        </h2>
        <p className="mb-5 text-sm text-gray-500">
          Have an existing resume? Upload it and the interview will build on
          what you already have. Supports PDF, DOCX, and TXT.
        </p>

        <div
          className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 px-6 py-10 text-center hover:border-brand-dark"
          onClick={() => fileRef.current?.click()}
        >
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.txt"
            className="hidden"
            onChange={handleFile}
          />
          {file ? (
            <p className="text-sm font-medium text-brand-dark">{file.name}</p>
          ) : (
            <>
              <p className="text-sm font-medium text-gray-600">
                Click to choose a file
              </p>
              <p className="mt-1 text-xs text-gray-400">PDF, DOCX, or TXT</p>
            </>
          )}
        </div>

        {error && (
          <p className="mt-3 text-sm text-red-500">{error}</p>
        )}

        <div className="mt-5 flex items-center justify-end gap-3">
          <button
            onClick={() => onDone(false)}
            className="rounded-lg px-4 py-2 text-sm text-gray-500 hover:text-gray-700"
          >
            Skip for now
          </button>
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="rounded-lg bg-brand-dark px-4 py-2 text-sm font-medium text-white hover:bg-opacity-90 disabled:opacity-40"
          >
            {uploading ? "Uploading…" : "Upload Resume"}
          </button>
        </div>
      </div>
    </div>
  );
}
