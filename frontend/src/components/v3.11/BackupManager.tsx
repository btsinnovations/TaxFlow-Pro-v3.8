import { useState } from "react";
import ModuleShell from "./ModuleShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { exportBackup, importBackup } from "@/hooks/useAPIExtensions";
import { Download, Upload, Loader2, AlertTriangle, CheckCircle2 } from "lucide-react";

export default function BackupManager() {
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleExport() {
    setExporting(true);
    setError(null);
    setMessage(null);
    try {
      const blob = await exportBackup();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `taxflow-backup-${new Date().toISOString().split("T")[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setMessage("Backup exported successfully.");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setExporting(false);
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setError(null);
    setMessage(null);
    try {
      const res = await importBackup(file);
      setMessage(`Import complete: ${JSON.stringify(res)}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  }

  return (
    <ModuleShell title="Backup Manager" description="Export and import TaxFlow data backups." moduleId="M02">
      <div className="flex flex-col gap-6 max-w-xl">
        <div className="rounded-md border border-divider p-6">
          <h3 className="text-text-primary font-medium mb-2">Export Backup</h3>
          <p className="text-text-secondary text-sm mb-4">Download a full backup of all TaxFlow data as JSON.</p>
          <Button onClick={handleExport} disabled={exporting} className="bg-gold text-black hover:bg-gold/90">
            {exporting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Download className="w-4 h-4 mr-1" />}
            Export Backup
          </Button>
        </div>

        <div className="rounded-md border border-divider p-6">
          <h3 className="text-text-primary font-medium mb-2">Import Backup</h3>
          <p className="text-text-secondary text-sm mb-4">Restore data from a previously exported backup file.</p>
          <label className="flex items-center gap-2 cursor-pointer">
            <Button variant="outline" disabled={importing} className="border-gold/30 text-gold hover:bg-gold/10">
              {importing ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Upload className="w-4 h-4 mr-1" />}
              Select Backup File
            </Button>
            <Input type="file" accept=".json" onChange={handleImport} disabled={importing} className="hidden" />
            <span className="text-text-secondary text-sm">{importing ? "Importing..." : "No file selected"}</span>
          </label>
        </div>

        {message && (
          <div className="flex items-center gap-2 rounded-md border border-green-500/30 bg-green-500/10 p-3 text-sm text-green-300">
            <CheckCircle2 className="w-4 h-4" /> {message}
          </div>
        )}
        {error && (
          <div className="flex items-center gap-2 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
            <AlertTriangle className="w-4 h-4" /> {error}
          </div>
        )}
      </div>
    </ModuleShell>
  );
}