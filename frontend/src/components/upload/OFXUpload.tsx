import { useState, useRef, useCallback } from 'react';
import { Upload, FileText, AlertCircle, CheckCircle2, Loader2, Download } from 'lucide-react';
import { uploadOFX, getAccounts } from '@/hooks/useAPI';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

interface OFXUploadProps {
  onComplete?: (result: {
    statement_id: number;
    account_id: number;
    account_name: string;
    transactions_count: number;
    duplicates_skipped: number;
  }) => void;
}

export default function OFXUpload({ onComplete }: OFXUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string>('new');
  const [loadingAccounts, setLoadingAccounts] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<{
    statement_id: number;
    account_id: number;
    account_name: string;
    transactions_count: number;
    duplicates_skipped: number;
    period_start?: string;
    period_end?: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const loadAccounts = useCallback(async () => {
    setLoadingAccounts(true);
    try {
      const data = await getAccounts();
      setAccounts(data || []);
    } catch (e: any) {
      setError(e?.message || 'Failed to load accounts');
    } finally {
      setLoadingAccounts(false);
    }
  }, []);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFile = (f: File) => {
    if (!f.name.toLowerCase().endsWith('.ofx') && !f.name.toLowerCase().endsWith('.qfx')) {
      setError('Only .ofx and .qfx files are supported');
      return;
    }
    setError(null);
    setResult(null);
    setFile(f);
    loadAccounts();
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const accountId = selectedAccountId === 'new' ? null : Number(selectedAccountId);
      const res = await uploadOFX(file, accountId);
      setResult(res);
      if (onComplete) onComplete(res);
    } catch (e: any) {
      setError(e?.message || 'OFX import failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card className="bg-canvas border-gold/30">
      <CardHeader>
        <CardTitle className="text-text-primary flex items-center gap-2">
          <Upload className="w-5 h-5 text-gold" />
          OFX / QFX Import
        </CardTitle>
        <CardDescription className="text-text-secondary">
          Import transactions directly from Quicken/OFX files with automatic duplicate detection.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!result ? (
          <>
            <div
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                dragActive ? 'border-gold bg-gold/5' : 'border-divider hover:border-gold/50'
              }`}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".ofx,.qfx"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              />
              <Upload className="w-8 h-8 text-gold mx-auto mb-2" />
              <p className="text-text-primary font-medium">{file ? file.name : 'Drop an OFX/QFX file or click to browse'}</p>
              <p className="text-text-secondary text-sm mt-1">Supports Quicken, QuickBooks, and bank-exported OFX/QFX files.</p>
            </div>

            {file && (
              <div className="space-y-4">
                <div className="space-y-1">
                  <label className="text-sm text-text-secondary">Map to existing account or create new</label>
                  <Select value={selectedAccountId} onValueChange={setSelectedAccountId} disabled={loadingAccounts}>
                    <SelectTrigger className="border-gold/30 bg-canvas text-text-primary">
                      <SelectValue placeholder={loadingAccounts ? 'Loading accounts...' : 'Select account'} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="new">➕ Create new account from OFX</SelectItem>
                      {accounts.map((a) => (
                        <SelectItem key={a.id} value={String(a.id)}>
                          {a.name} ({a.type || a.account_type || 'unknown'})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <Button
                  onClick={handleUpload}
                  disabled={uploading}
                  className="w-full bg-gold text-black hover:bg-gold/90"
                >
                  {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
                  Import {file.name}
                </Button>
              </div>
            )}
          </>
        ) : (
          <div className="rounded-lg border border-gold/30 bg-gold/5 p-6 space-y-4">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-6 h-6 text-emerald-400" />
              <span className="text-lg text-text-primary">Import complete</span>
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-text-secondary">Account</p>
                <p className="text-text-primary">{result.account_name}</p>
              </div>
              <div>
                <p className="text-text-secondary">Transactions imported</p>
                <p className="text-text-primary">{result.transactions_count}</p>
              </div>
              <div>
                <p className="text-text-secondary">Duplicates skipped</p>
                <p className="text-text-primary">{result.duplicates_skipped}</p>
              </div>
              <div>
                <p className="text-text-secondary">Period</p>
                <p className="text-text-primary">{result.period_start || '—'} → {result.period_end || '—'}</p>
              </div>
            </div>
            <div className="flex gap-3">
              <Button
                variant="outline"
                className="border-gold/30 text-gold hover:bg-gold/10"
                onClick={() => {
                  const blob = new Blob(
                    [JSON.stringify(result, null, 2)],
                    { type: 'application/json' }
                  );
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `ofx-import-${result.statement_id}.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                <Download className="w-4 h-4 mr-1" />
                Export summary
              </Button>
              <Button
                className="bg-gold text-black hover:bg-gold/90"
                onClick={() => { setResult(null); setFile(null); setSelectedAccountId('new'); }}
              >
                Import another
              </Button>
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
