import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getInvoices } from "@/hooks/useAPIExtensions";

export default function InvoicingManager() {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getInvoices()
      .then(setInvoices)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Invoicing"
      description="Create and manage customer invoices and payments."
      moduleId="M18"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {invoices.map((i: any) => (
            <pre key={i.id} className="rounded border border-divider p-3 text-xs text-text-secondary">{JSON.stringify(i, null, 2)}</pre>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
