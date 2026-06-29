import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getGlEntries } from "@/hooks/useAPIExtensions";

export default function GLManager() {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getGlEntries()
      .then(setEntries)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="General Ledger"
      description="View and manage GL entries."
      moduleId="M06"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {entries.map((e: any) => (
            <pre key={e.id} className="rounded border border-divider p-3 text-xs text-text-secondary">{JSON.stringify(e, null, 2)}</pre>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
