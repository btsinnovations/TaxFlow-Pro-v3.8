import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getImports } from "@/hooks/useAPIExtensions";

export default function ImportsManager() {
  const [imports, setImports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getImports()
      .then(setImports)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Import Center"
      description="Review statement and transaction import history."
      moduleId="M07"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {imports.map((i: any) => (
            <pre key={i.id} className="rounded border border-divider p-3 text-xs text-text-secondary">{JSON.stringify(i, null, 2)}</pre>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
