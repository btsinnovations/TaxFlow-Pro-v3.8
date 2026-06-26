import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Download, FileText, AlertTriangle } from 'lucide-react';
import FileDropzone from '../components/FileDropzone';
import { uploadFile, processFile, downloadResult, getClients } from '../hooks/useAPI';
import { useToast } from "@/hooks/useToast";
import OFXUpload from '../components/upload/OFXUpload';

const UploadSection = () => {
  const [clientId, setClientId] = useState('default');
  const [format, setFormat] = useState<'qif' | 'csv' | 'json'>('qif');
  const [useFast, setUseFast] = useState(false);
  const [useOcr, setUseOcr] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [results, setResults] = useState<any[]>([]);
  const [clients, setClients] = useState<any[]>([]);
  const [loadingClients, setLoadingClients] = useState(true);

  useEffect(() => {
    getClients().then(setClients).catch(() => setClients([])).finally(() => setLoadingClients(false));
  }, []);

  const { addToast } = useToast();
  // suppress unused warning for now
  void addToast;

  const runUpload = async (files: File[]) => {
    const newResults: any[] = [];
    for (const file of files) {
      try {
        const isPdf = file.name.toLowerCase().endsWith('.pdf');
        const uploadRes = await uploadFile(file, clientId, isPdf && useOcr);
        const processRes = await processFile(uploadRes.file_id, {
          client_id: clientId,
          output_format: format,
          use_fast: useFast,
        });
        newResults.push({
          filename: file.name,
          fileId: uploadRes.file_id,
          success: processRes.success,
          transactions: processRes.transaction_count,
          institution: processRes.institution,
          reconciliation: processRes.reconciliation?.status,
          outputFile: processRes.output_file,
          warnings: processRes.warnings || [],
        });
      } catch (err) {
        newResults.push({
          filename: file.name,
          success: false,
          error: err instanceof Error ? err.message : 'Unknown error',
        });
      }
    }
    setResults(newResults);
    window.location.reload();
  };

  const handleUpload = async (files: File[]) => {
    setPendingFiles(files);
    await runUpload(files);
  };

  const handleDownload = async (fileId: string, filename?: string) => {
    try {
      const blob = await downloadResult(fileId, format);
      if (!blob || blob.size === 0) {
        console.error('Download failed: empty blob');
        alert('Download failed: file not found or empty');
        return;
      }
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'csv' ? 'csv' : 'qif';
      a.download = filename || `processed_${fileId}.${ext}`;
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download error:', err);
      alert('Download failed. Check console for details.');
    }
  };

  return (
    <section id="upload" className="py-24 px-6 bg-[#0C0C0C]">
      <div className="max-w-4xl mx-auto">
        <div className="mb-12">
          <h2 className="font-serif text-4xl md:text-5xl text-white mb-4">Upload Statements</h2>
          <p className="text-white/50">
            Drag and drop PDF or CSV bank statements. Processing is 100% offline.
            <span className="text-[#C9A96E]"> Both PDF and CSV are fully supported.</span>
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <Card className="bg-white/[0.02] border-white/10">
            <CardHeader>
              <CardTitle className="text-white text-sm flex items-center gap-2">
                <FileText className="w-4 h-4 text-[#C9A96E]" />
                Client
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Select value={clientId} onValueChange={setClientId} disabled={loadingClients}>
                <SelectTrigger className="bg-white/5 border-white/10 text-white">
                  <SelectValue placeholder={loadingClients ? "Loading..." : "Select client"} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">Default (No Client)</SelectItem>
                  {clients.map((c) => (
                    <SelectItem key={c.id} value={c.id}>{c.name} ({c.entity_type})</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          <Card className="bg-white/[0.02] border-white/10">
            <CardHeader>
              <CardTitle className="text-white text-sm">Output Format</CardTitle>
            </CardHeader>
            <CardContent>
              <Select value={format} onValueChange={(v) => setFormat(v as any)}>
                <SelectTrigger className="bg-white/5 border-white/10 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="qif">QIF</SelectItem>
                  <SelectItem value="csv">CSV</SelectItem>
                  <SelectItem value="json">JSON</SelectItem>
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          <Card className="bg-white/[0.02] border-white/10">
            <CardHeader>
              <CardTitle className="text-white text-sm">Options</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <Label className="text-white/70 text-sm">Fast Mode (skip OCR)</Label>
                <Switch checked={useFast} onCheckedChange={setUseFast} />
              </div>
              <p className="text-white/30 text-xs">
                Use for digital PDFs. Skips OCR and extracts text directly.
              </p>
              <div className="flex items-center justify-between">
                <Label className="text-white/70 text-sm">Use OCR</Label>
                <Switch checked={useOcr} onCheckedChange={setUseOcr} />
              </div>
              <p className="text-white/30 text-xs">
                Force Tesseract OCR on PDFs with scanned pages. Requires Tesseract + Poppler.
              </p>
            </CardContent>
          </Card>
        </div>

        <FileDropzone onUpload={handleUpload} />

        <div className="mt-12">
          <OFXUpload />
        </div>

        {pendingFiles.length > 0 && (
          <div className="mt-4 p-3 rounded-lg bg-white/[0.03] border border-white/10">
            <p className="text-white/70 text-sm mb-2">Pending upload ({pendingFiles.length}):</p>
            <div className="flex flex-wrap gap-2">
              {pendingFiles.map((f, i) => (
                <span key={i} className="text-xs text-white/50 bg-white/5 px-2 py-1 rounded">
                  {f.name} {f.name.toLowerCase().endsWith('.pdf') && useOcr ? '(OCR)' : ''}
                </span>
              ))}
            </div>
          </div>
        )}

        {results.length > 0 && (
          <div className="mt-8 space-y-4">
            <h3 className="text-white font-medium text-lg">Processing Results</h3>
            {results.map((r, i) => (
              <div
                key={i}
                className={`p-4 rounded-lg border ${r.success ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-red-500/30 bg-red-500/5'}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-white font-medium">{r.filename}</span>
                  <span className={`text-xs px-2 py-1 rounded font-medium ${
                    r.success ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                  }`}>
                    {r.success ? 'SUCCESS' : 'FAILED'}
                  </span>
                </div>

                {r.success ? (
                  <div className="text-white/60 text-sm space-y-1">
                    <p>Institution: <span className="text-white/90">{r.institution}</span></p>
                    <p>Transactions: <span className="text-white/90">{r.transactions}</span></p>
                    <p>Reconciliation: <span className={
                      r.reconciliation === 'PASS' ? 'text-emerald-400' :
                      r.reconciliation === 'FAIL' ? 'text-red-400' : 'text-amber-400'
                    }>{r.reconciliation}</span></p>

                    {r.warnings.length > 0 && (
                      <div className="flex items-start gap-2 mt-2 p-2 bg-amber-500/10 rounded border border-amber-500/20">
                        <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                        <p className="text-amber-400/80 text-xs">{r.warnings[0]}</p>
                      </div>
                    )}

                    {r.outputFile && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-3 border-[#C9A96E]/30 text-[#C9A96E] hover:bg-[#C9A96E]/10"
                        onClick={() => handleDownload(r.fileId)}
                      >
                        <Download className="w-4 h-4 mr-2" />
                        Download {format.toUpperCase()}
                      </Button>
                    )}
                  </div>
                ) : (
                  <p className="text-red-400 text-sm">{r.error}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
};

export default UploadSection;
