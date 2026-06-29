import { useState } from "react";
import ModuleShell from "./ModuleShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { uploadFile } from "@/hooks/useAPIExtensions";
import { Upload, Loader2, AlertTriangle, CheckCircle2 } from "lucide-react";

export default function UploadManager() {
  const [file, setFile] = useState<File | null>(null);
  const [clientId, setClientId] = useState("default");
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError(null);
    setMessage(null);
    try {
      const res = await uploadFile(file, clientId);
      setMessage(`Upload complete: ${JSON.stringify(res).slice(0, 300)}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <ModuleShell title="Upload Manager" description="Upload documents and statements to TaxFlow Pro." moduleId="M19">
      <div className="max-w-lg space-y-4">
        <div>
          <Label className="text-text-secondary">Client ID</Label>
          <Input value={clientId} onChange={(e) => setClientId(e.target.value)} className="border-gold/30 bg-canvas text-text-primary" />
        </div>

        <div>
          <Label className="text-text-secondary">File</Label>
          <Input type="file" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setMessage(null); setError(null); }} className="border-gold/30 bg-canvas text-text-primary" />
          {file && <p className="text-text-secondary text-sm mt-1">{file.name} ({(file.size / 1024).toFixed(1)} KB)</p>}
        </div>

        <Button onClick={handleUpload} disabled={!file || uploading} className="bg-gold text-black hover:bg-gold/90">
          {uploading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Upload className="w-4 h-4 mr-1" />}
          Upload
        </Button>

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