import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getLiabilities } from "@/hooks/useAPIExtensions";

export default function LiabilitiesManager() {
  const [liabilities, setLiabilities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getLiabilities()
      .then(setLiabilities)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Liabilities"
      description="Track loans, credit cards, and other liabilities."
      moduleId="M19"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {liabilities.map((l: any) => (
            <pre key={l.id} className="rounded border border-divider p-3 text-xs text-text-secondary">{JSON.stringify(l, null, 2)}</pre>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
