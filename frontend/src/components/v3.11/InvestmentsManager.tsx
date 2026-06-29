import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getInvestments } from "@/hooks/useAPIExtensions";

export default function InvestmentsManager() {
  const [investments, setInvestments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getInvestments()
      .then(setInvestments)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Investments"
      description="Track investment accounts and lots."
      moduleId="M17"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {investments.map((i: any) => (
            <pre key={i.id} className="rounded border border-divider p-3 text-xs text-text-secondary">{JSON.stringify(i, null, 2)}</pre>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
