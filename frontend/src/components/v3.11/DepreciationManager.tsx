import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getDepreciationAssets } from "@/hooks/useAPIExtensions";

export default function DepreciationManager() {
  const [assets, setAssets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDepreciationAssets()
      .then(setAssets)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Depreciation"
      description="Manage depreciable assets and schedules."
      moduleId="M04"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {assets.map((a: any) => (
            <pre key={a.id} className="rounded border border-divider p-3 text-xs text-text-secondary">{JSON.stringify(a, null, 2)}</pre>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
