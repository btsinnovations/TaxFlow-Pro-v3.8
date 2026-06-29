import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getCoaAccounts } from "@/hooks/useAPIExtensions";

export default function COAManager() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCoaAccounts()
      .then(setAccounts)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Chart of Accounts"
      description="Manage the chart of accounts hierarchy."
      moduleId="M21"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {accounts.map((a: any) => (
            <pre key={a.id} className="rounded border border-divider p-3 text-xs text-text-secondary">{JSON.stringify(a, null, 2)}</pre>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
