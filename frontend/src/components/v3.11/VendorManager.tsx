import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getVendors } from "@/hooks/useAPIExtensions";

export default function VendorManager() {
  const [vendors, setVendors] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getVendors()
      .then(setVendors)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Vendors"
      description="Manage vendor list and 1099 tracking."
      moduleId="M13"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <div className="space-y-2">
          {vendors.map((v: any) => (
            <pre key={v.id} className="rounded border border-divider p-3 text-xs text-text-secondary">{JSON.stringify(v, null, 2)}</pre>
          ))}
        </div>
      )}
    </ModuleShell>
  );
}
