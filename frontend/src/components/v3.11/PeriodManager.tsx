import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getPeriods } from "@/hooks/useAPIExtensions";

export default function PeriodManager() {
  const [periods, setPeriods] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPeriods()
      .then(setPeriods)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Accounting Periods"
      description="Open, close, and review fiscal periods."
      moduleId="M09"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {periods.map((p: any) => (
            <pre key={p.id} className="rounded border border-divider p-3 text-xs text-text-secondary">{JSON.stringify(p, null, 2)}</pre>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
