import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getAuditLog } from "@/hooks/useAPIExtensions";

export default function AuditManager() {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAuditLog(50)
      .then(setEntries)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Audit Log"
      description="View system audit events and changes."
      moduleId="M01"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {entries.map((e: any) => (
            <div key={e.id} className="rounded border border-divider p-3">
              <pre className="text-xs text-text-secondary">{JSON.stringify(e, null, 2)}</pre>
            </div>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
