import { useEffect, useState, useRef, useCallback } from 'react';
import {
  ReceiptText, Upload, Trash2, Search, Link, AlertCircle,
  FileText, Eye,
} from 'lucide-react';
import {
  uploadReceipt, getReceipts, deleteReceipt, matchReceipt,
} from '@/hooks/useAPI';
import { useClient } from '@/context/ClientContext';
import { useToast } from '@/hooks/useToast';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface Receipt {
  id: number;
  tenant_id: number;
  user_id: number;
  transaction_id: number | null;
  filename: string;
  file_path: string;
  ocr_text: string | null;
  vendor: string | null;
  amount: number | null;
  receipt_date: string | null;
  created_at: string;
}

interface MatchResult {
  transaction_id: number;
  confidence: number;
  factors: { amount: number; date: number; description: number };
}

export default function ReceiptsPage() {
  const { selectedClient } = useClient();
  const { toast } = useToast();
  const sectionRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  // Upload form
  const [uploadForm, setUploadForm] = useState({
    vendor: '',
    amount: '',
    receipt_date: '',
    file: null as File | null,
  });

  // Detail dialog
  const [selectedReceipt, setSelectedReceipt] = useState<Receipt | null>(null);
  const [matches, setMatches] = useState<MatchResult[]>([]);
  const [matchLoading, setMatchLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!selectedClient) return;
    setLoading(true);
    try {
      const data = await getReceipts(selectedClient.id);
      setReceipts(data);
    } catch {
      setError('Failed to load receipts');
    } finally {
      setLoading(false);
    }
  }, [selectedClient]);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo(
        sectionRef.current,
        { opacity: 0, y: 30 },
        {
          opacity: 1, y: 0, duration: 0.5, ease: 'power3.out',
          scrollTrigger: { trigger: sectionRef.current, start: 'top 80%', toggleActions: 'play none none none' },
        }
      );
    }, sectionRef);
    return () => ctx.revert();
  }, [loading, receipts]);

  const formatCurrency = (v: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Math.abs(v));

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setUploadForm(f => ({ ...f, file }));
  };

  const handleUpload = async () => {
    if (!selectedClient || !uploadForm.file) return;
    setUploading(true);
    setError('');
    try {
      await uploadReceipt(selectedClient.id, uploadForm.file, {
        vendor: uploadForm.vendor || undefined,
        amount: uploadForm.amount ? parseFloat(uploadForm.amount) : undefined,
        receipt_date: uploadForm.receipt_date || undefined,
      });
      toast({ title: 'Receipt uploaded', description: uploadForm.file.name });
      setUploadForm({ vendor: '', amount: '', receipt_date: '', file: null });
      if (fileInputRef.current) fileInputRef.current.value = '';
      fetchData();
    } catch (e: any) {
      setError(e.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (receiptId: number) => {
    try {
      await deleteReceipt(receiptId);
      toast({ title: 'Receipt deleted' });
      if (selectedReceipt?.id === receiptId) setSelectedReceipt(null);
      fetchData();
    } catch (e: any) {
      setError(e.message || 'Delete failed');
    }
  };

  const handleMatch = async (receipt: Receipt) => {
    if (!selectedClient) return;
    setMatchLoading(true);
    try {
      const results = await matchReceipt(receipt.id, selectedClient.id);
      setSelectedReceipt(receipt);
      setMatches(results);
    } catch (e: any) {
      setError(e.message || 'Match failed');
    } finally {
      setMatchLoading(false);
    }
  };

  const filtered = receipts.filter(r => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (r.vendor || '').toLowerCase().includes(s) ||
           (r.filename || '').toLowerCase().includes(s) ||
           (r.ocr_text || '').toLowerCase().includes(s);
  });

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
            <ReceiptText className="text-gold" size={28} />
            Receipts
          </h1>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Upload receipt images or PDFs, view extracted details, and match receipts to transactions.
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20 mb-6">
            <AlertCircle size={16} />{error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Upload Form */}
          <Card className="bg-surface border-divider lg:col-span-1">
            <CardHeader>
              <CardTitle className="font-sans text-sm font-medium text-text-primary flex items-center gap-2">
                <Upload size={16} className="text-gold" />
                Upload Receipt
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="font-sans text-xs text-text-secondary">File (JPG, PNG, PDF, etc.)</Label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".jpg,.jpeg,.png,.gif,.pdf,.tiff,.bmp,.webp"
                  onChange={handleFileSelect}
                  className="w-full text-xs text-text-secondary"
                />
                {uploadForm.file && (
                  <p className="font-mono text-xs text-gold mt-1">{uploadForm.file.name}</p>
                )}
              </div>
              <div>
                <Label className="font-sans text-xs text-text-secondary">Vendor</Label>
                <Input
                  value={uploadForm.vendor}
                  onChange={e => setUploadForm(f => ({ ...f, vendor: e.target.value }))}
                  placeholder="e.g. Office Depot"
                  className="bg-canvas border-divider text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="font-sans text-xs text-text-secondary">Amount ($)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={uploadForm.amount}
                    onChange={e => setUploadForm(f => ({ ...f, amount: e.target.value }))}
                    placeholder="0.00"
                    className="bg-canvas border-divider text-sm"
                  />
                </div>
                <div>
                  <Label className="font-sans text-xs text-text-secondary">Date</Label>
                  <Input
                    type="date"
                    value={uploadForm.receipt_date}
                    onChange={e => setUploadForm(f => ({ ...f, receipt_date: e.target.value }))}
                    className="bg-canvas border-divider text-sm"
                  />
                </div>
              </div>
              <Button
                className="w-full bg-gold text-black hover:bg-gold/90"
                onClick={handleUpload}
                disabled={uploading || !uploadForm.file}
              >
                {uploading ? 'Uploading...' : 'Upload Receipt'}
              </Button>
            </CardContent>
          </Card>

          {/* Receipt List */}
          <div className="lg:col-span-2">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex-1 relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
                <Input
                  placeholder="Search receipts..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="pl-9 bg-surface border-divider text-sm"
                />
              </div>
              <Badge variant="outline" className="text-xs border-text-secondary/30 text-text-secondary">
                {filtered.length} receipt(s)
              </Badge>
            </div>

            {loading ? (
              <div className="text-text-secondary text-sm">Loading receipts...</div>
            ) : filtered.length === 0 ? (
              <Card className="bg-surface border-divider">
                <CardContent className="p-8 text-center">
                  <FileText size={32} className="text-text-secondary mx-auto mb-3" />
                  <p className="text-text-secondary font-sans text-sm">No receipts uploaded yet.</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-3">
                {filtered.map(r => (
                  <Card key={r.id} className="bg-surface border-divider">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <FileText size={14} className="text-gold" />
                            <span className="font-sans text-sm text-text-primary truncate">{r.filename}</span>
                            {r.transaction_id && (
                              <Badge variant="outline" className="text-xs border-emerald-400/30 text-emerald-400">
                                <Link size={10} className="mr-1" /> Matched
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-4 text-xs text-text-secondary">
                            {r.vendor && <span>Vendor: {r.vendor}</span>}
                            {r.amount !== null && <span className="font-mono text-amber-400">{formatCurrency(r.amount)}</span>}
                            {r.receipt_date && <span>{r.receipt_date}</span>}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 ml-4">
                          <Button size="sm" variant="ghost" className="h-7 text-xs text-gold" onClick={() => handleMatch(r)}>
                            <Eye size={12} className="mr-1" /> Match
                          </Button>
                          <Button size="sm" variant="ghost" className="h-7 w-7 text-red-400" onClick={() => handleDelete(r.id)}>
                            <Trash2 size={14} />
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Match Dialog */}
      <Dialog open={!!selectedReceipt} onOpenChange={(open) => { if (!open) { setSelectedReceipt(null); setMatches([]); } }}>
        <DialogContent className="bg-surface border-divider text-text-primary max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-sans text-sm flex items-center gap-2">
              <Link size={16} className="text-gold" />
              Match Receipt: {selectedReceipt?.filename}
            </DialogTitle>
          </DialogHeader>
          {matchLoading ? (
            <div className="py-8 text-center text-text-secondary text-sm">Finding matching transactions...</div>
          ) : matches.length > 0 ? (
            <div className="space-y-3 py-2">
              {matches.map((m) => (
                <div key={m.transaction_id} className="bg-canvas rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-sm text-text-primary">Transaction #{m.transaction_id}</span>
                    <Badge className={`text-xs ${m.confidence >= 70 ? 'bg-emerald-400/20 text-emerald-400' : m.confidence >= 40 ? 'bg-amber-400/20 text-amber-400' : 'bg-red-400/20 text-red-400'}`}>
                      {m.confidence.toFixed(0)}% confidence
                    </Badge>
                  </div>
                  <Progress value={m.confidence} className="h-1.5 mb-2" />
                  <div className="flex gap-4 text-[11px] text-text-secondary font-mono">
                    <span>Amount: {m.factors.amount.toFixed(0)}%</span>
                    <span>Date: {m.factors.date.toFixed(0)}%</span>
                    <span>Desc: {m.factors.description.toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : selectedReceipt ? (
            <div className="py-8 text-center text-text-secondary text-sm">No matching transactions found.</div>
          ) : null}
          <DialogFooter>
            <Button onClick={() => { setSelectedReceipt(null); setMatches([]); }}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
