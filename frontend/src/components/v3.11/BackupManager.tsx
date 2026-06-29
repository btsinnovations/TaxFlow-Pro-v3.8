import ModuleShell from "./ModuleShell";
import { useEffect, useState } from "react";
import { listBackups, createBackup } from "@/hooks/useAPIExtensions";

export default function BackupManager() {
  const [backups, setBackups] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listBackups()
      .then(setBackups)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleBackup = () => {
    createBackup().then(() => listBackups().then(setBackups));
  };

  return (
    <ModuleShell
      title="Backup & Restore"
      description="Create and manage database backups."
      moduleId="M02"
    >
      <button
        onClick={handleBackup}
        className="rounded bg-gold px-4 py-2 text-canvas hover:bg-gold/90"
      >
        Create Backup
      </button>
      {loading && <p className="text-text-secondary">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      {!loading && !error && (
        <ul className="mt-4 space-y-2">
          {backups.map((b: any) => (
            <li key={b.id} className="rounded border border-divider p-3 text-sm text-text-secondary">
              {JSON.stringify(b)}
            </li>
          ))}
        </ul>
      )}
    </ModuleShell>
  );
}
