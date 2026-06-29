import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getSalesTax } from "@/hooks/useAPIExtensions";

export default function SalesTaxManager() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSalesTax()
      .then(setItems)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Sales Tax"
      description="Manage sales tax liabilities and payments."
      moduleId="M11"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {items.map((i: any) => (
            <pre key={i.id} className="rounded border border-divider p-3 text-xs text-text-secondary">{JSON.stringify(i, null, 2)}</pre>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
