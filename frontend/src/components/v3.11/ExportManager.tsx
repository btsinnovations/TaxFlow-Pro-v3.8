import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getExportFormats } from "@/hooks/useAPIExtensions";

export default function ExportManager() {
  const [formats, setFormats] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getExportFormats()
      .then(setFormats)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Data Exports"
      description="Export transactions, reports, and tax forms."
      moduleId="M16"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {formats.map((f: any) => (
            <pre key={f.id ?? f.name} className="rounded border border-divider p-3 text-xs text-text-secondary">{JSON.stringify(f, null, 2)}</pre>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
