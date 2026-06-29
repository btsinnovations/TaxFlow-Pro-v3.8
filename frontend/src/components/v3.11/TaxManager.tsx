import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getTaxRules } from "@/hooks/useAPIExtensions";

export default function TaxManager() {
  const [rules, setRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTaxRules()
      .then(setRules)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Tax Rules"
      description="Manage tax line mappings and rules."
      moduleId="M12"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {rules.map((r: any) => (
            <pre key={r.id} className="rounded border border-divider p-3 text-xs text-text-secondary">{JSON.stringify(r, null, 2)}</pre>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
