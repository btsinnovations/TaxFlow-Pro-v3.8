import ModuleShell from "./ModuleShell";
import { useState } from "react";
import { uploadFile } from "@/hooks/useAPIExtensions";

export default function UploadManager() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const handleUpload = async () => {
    if (!file) return;
    setStatus("Uploading...");
    try {
      await uploadFile(file);
      setStatus("Upload complete");
    } catch (err: any) {
      setStatus(`Error: ${err.message}`);
    }
  };

  return (
    <ModuleShell
      title="Upload Manager"
      description="Upload bank statements, receipts, and tax documents."
      moduleId="M20"
    >
      <input
        type="file"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="block w-full rounded border border-divider bg-canvas p-2 text-sm text-text-secondary"
      />
      <button
        onClick={handleUpload}
        disabled={!file}
        className="mt-4 rounded bg-gold px-4 py-2 text-canvas hover:bg-gold/90 disabled:opacity-50"
      >
        Upload
      </button>
      {status && <p className="mt-4 text-text-secondary">{status}</p>}
    </ModuleShell>
  );
}
