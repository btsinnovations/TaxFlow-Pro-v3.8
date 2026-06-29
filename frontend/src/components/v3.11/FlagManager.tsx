import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getFlags } from "@/hooks/useAPIExtensions";

export default function FlagManager() {
  const [flags, setFlags] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getFlags()
      .then(setFlags)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Transaction Flags"
      description="Review and manage flagged transactions."
      moduleId="M05"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {flags.map((f: any) => (
            <pre key={f.id} className="rounded border border-divider p-3 text-xs text-text-secondary">{JSON.stringify(f, null, 2)}</pre>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
