import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getClients } from "@/hooks/useAPIExtensions";

export default function ClientManager() {
  const [clients, setClients] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getClients()
      .then(setClients)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Client Management"
      description="Manage clients and business entities."
      moduleId="M15"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {clients.map((c: any) => (
            <pre key={c.id} className="rounded border border-divider p-3 text-xs text-text-secondary">{JSON.stringify(c, null, 2)}</pre>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
