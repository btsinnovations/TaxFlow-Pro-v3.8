import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getRules } from "@/hooks/useAPIExtensions";

export default function RuleManager() {
  const [rules, setRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRules()
      .then(setRules)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Categorization Rules"
      description="Create and manage auto-categorization rules."
      moduleId="M10"
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
