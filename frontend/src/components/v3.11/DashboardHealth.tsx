import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getHealth } from "@/hooks/useAPIExtensions";

export default function DashboardHealth() {
  const [health, setHealth] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="System Health"
      description="Backend health status and runtime diagnostics."
      moduleId="M03"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && health && (
        <pre className="rounded border border-divider p-4 text-xs text-text-secondary">{JSON.stringify(health, null, 2)}</pre>
      )}
    </ModuleShell>
  );
}
