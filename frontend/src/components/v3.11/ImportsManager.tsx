import { useState } from "react";
import ModuleShell from "./ModuleShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { detectInstitution, importOfx } from "@/hooks/useAPIExtensions";
import { Upload, Loader2, AlertTriangle, CheckCircle2, Building2 } from "lucide-react";

export default function ImportsManager() {
  const [file, setFile] = useState<File | null>(null);
  const [clientId, setClientId] = useState("");
  const [detecting, setDetecting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [detection, setDetection] = useState<any | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleDetect() {
    if (!file) return;
    setDetecting(true);
    setError(null);
    setMessage(null);
    try {
      const res = await detectInstitution(file);
      setDetection(res);
      setMessage(`Detected: ${res?.institution ?? res?.name ?? "Unknown"}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setDetecting(false);
    }
  }

  async function handleImport() {
    if (!file) return;
    setImporting(true);
    setError(null);
    setMessage(null);
    try {
      const res = await importOfx(file, clientId || undefined);
      setMessage(`Import complete: ${JSON.stringify(res).slice(0, 300)}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setImporting(false);
    }
  }

  return (
    <ModuleShell title="Imports Manager" description="Detect financial institution and import OFX/QFX files." moduleId="M10">
      <div className="max-w-lg space-y-4">
        <div>
          <label className="block text-sm text-text-secondary mb-1">Client ID (optional)</label>
          <Input value={clientId} onChange={(e) => setClientId(e.target.value)} placeholder="default" className="border-gold/30 bg-canvas text-text-primary" />
        </div>

        <div>
          <label className="block text-sm text-text-secondary mb-1">Statement file (OFX/QFX)</label>
          <Input type="file" accept=".ofx,.qfx" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setDetection(null); setMessage(null); setError(null); }} className="border-gold/30 bg-canvas text-text-primary" />
          {file && <p className="text-text-secondary text-sm mt-1">{file.name}</p>}
        </div>

        <div className="flex gap-2">
          <Button onClick={handleDetect} disabled={!file || detecting} variant="outline" className="border-gold/30 text-gold hover:bg-gold/10">
            {detecting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Building2 className="w-4 h-4 mr-1" />}
            Detect Institution
          </Button>
          <Button onClick={handleImport} disabled={!file || importing} className="bg-gold text-black hover:bg-gold/90">
            {importing ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Upload className="w-4 h-4 mr-1" />}
            Import OFX
          </Button>
        </div>

        {detection && (
          <div className="rounded-md border border-gold/30 bg-gold/5 p-4">
            <p className="text-text-primary text-sm font-medium mb-2">Detection Result</p>
            <pre className="text-xs text-text-secondary whitespace-pre-wrap">{JSON.stringify(detection, null, 2)}</pre>
          </div>
        )}

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