import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getMileageEntries } from "@/hooks/useAPIExtensions";

export default function MileageLog() {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMileageEntries()
      .then(setEntries)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Mileage Log"
      description="Track business mileage for tax deductions."
      moduleId="M08"
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
