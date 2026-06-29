import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { getYearEndPackage } from "@/hooks/useAPIExtensions";

export default function YearEndManager() {
  const [pkg, setPkg] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getYearEndPackage()
      .then(setPkg)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ModuleShell
      title="Year-End Package"
      description="Generate and review the annual tax package."
      moduleId="M14"
    >
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && pkg && (
        <pre className="rounded border border-divider p-4 text-xs text-text-secondary">{JSON.stringify(pkg, null, 2)}</pre>
      )}
    </ModuleShell>
  );
}
