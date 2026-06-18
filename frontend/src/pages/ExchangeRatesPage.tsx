import { useEffect, useState, useRef, useCallback } from 'react';
import {
  Coins, Plus, ArrowRightLeft, Search, AlertCircle, Upload,
} from 'lucide-react';
import {
  getExchangeRates, createExchangeRate, convertCurrency, importExchangeRates,
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
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface ExchangeRate {
  id: number;
  from_currency: string;
  to_currency: string;
  rate: number;
  rate_date: string;
  source: string;
}

export default function ExchangeRatesPage() {
  const { selectedClient } = useClient();
  const { toast } = useToast();
  const sectionRef = useRef<HTMLDivElement>(null);

  const [rates, setRates] = useState<ExchangeRate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Add rate dialog
  const [addOpen, setAddOpen] = useState(false);
  const [addForm, setAddForm] = useState({
    from_currency: 'USD',
    to_currency: 'EUR',
    rate: '',
    rate_date: new Date().toISOString().slice(0, 10),
    source: 'manual',
  });

  // Converter
  const [convertForm, setConvertForm] = useState({
    from_currency: 'USD',
    to_currency: 'EUR',
    amount: '1000',
    rate_date: '',
  });
  const [convertResult, setConvertResult] = useState<any>(null);
  const [converting, setConverting] = useState(false);

  // Bulk import
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkText, setBulkText] = useState('');
  const [bulkLoading, setBulkLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!selectedClient) return;
    setLoading(true);
    try {
      const data = await getExchangeRates(selectedClient.id, { limit: 200 });
      setRates(data);
    } catch {
      setError('Failed to load exchange rates');
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
  }, [loading, rates]);

  const handleAdd = async () => {
    if (!selectedClient || !addForm.rate) return;
    try {
      await createExchangeRate(selectedClient.id, {
        from_currency: addForm.from_currency,
        to_currency: addForm.to_currency,
        rate: parseFloat(addForm.rate),
        rate_date: addForm.rate_date,
        source: addForm.source,
      });
      toast({ title: 'Rate added', description: `${addForm.from_currency}/${addForm.to_currency} = ${addForm.rate}` });
      setAddOpen(false);
      fetchData();
    } catch (e: any) {
      toast({ title: 'Failed', description: e.message, variant: 'destructive' });
    }
  };

  const handleConvert = async () => {
    if (!selectedClient || !convertForm.amount) return;
    setConverting(true);
    try {
      const result = await convertCurrency(selectedClient.id, {
        from_currency: convertForm.from_currency,
        to_currency: convertForm.to_currency,
        amount: parseFloat(convertForm.amount),
        rate_date: convertForm.rate_date || undefined,
      });
      setConvertResult(result);
    } catch (e: any) {
      toast({ title: 'Conversion failed', description: e.message, variant: 'destructive' });
    } finally {
      setConverting(false);
    }
  };

  const handleBulkImport = async () => {
    if (!selectedClient || !bulkText.trim()) return;
    setBulkLoading(true);
    try {
      // Parse JSON array of rates
      const parsed = JSON.parse(bulkText);
      if (!Array.isArray(parsed)) throw new Error('Expected a JSON array');
      const result = await importExchangeRates(selectedClient.id, parsed);
      toast({
        title: 'Import completed',
        description: `${result.created} created, ${result.updated} updated, ${(result.errors || []).length} errors`,
      });
      setBulkOpen(false);
      setBulkText('');
      fetchData();
    } catch (e: any) {
      toast({ title: 'Import failed', description: e.message, variant: 'destructive' });
    } finally {
      setBulkLoading(false);
    }
  };

  const CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'INR', 'MXN', 'BRL', 'KRW'];

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
          <div>
            <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
              <Coins className="text-gold" size={28} />
              Exchange Rates
            </h1>
            <p className="font-sans text-sm text-text-secondary mt-1">
              Maintain currency exchange rates and convert amounts between currencies.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setBulkOpen(true)}>
              <Upload size={14} className="mr-1" /> Bulk Import
            </Button>
            <Button onClick={() => setAddOpen(true)} className="bg-gold text-black hover:bg-gold/90">
              <Plus size={16} className="mr-1" /> Add Rate
            </Button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20 mb-6">
            <AlertCircle size={16} />{error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Currency Converter */}
          <Card className="bg-surface border-divider">
            <CardHeader>
              <CardTitle className="font-sans text-sm font-medium text-text-primary flex items-center gap-2">
                <ArrowRightLeft size={16} className="text-gold" />
                Currency Converter
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="font-sans text-xs text-text-secondary">From</Label>
                  <Select value={convertForm.from_currency} onValueChange={v => setConvertForm(f => ({ ...f, from_currency: v }))}>
                    <SelectTrigger className="bg-canvas border-divider text-sm"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {CURRENCIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="font-sans text-xs text-text-secondary">To</Label>
                  <Select value={convertForm.to_currency} onValueChange={v => setConvertForm(f => ({ ...f, to_currency: v }))}>
                    <SelectTrigger className="bg-canvas border-divider text-sm"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {CURRENCIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label className="font-sans text-xs text-text-secondary">Amount</Label>
                <Input type="number" value={convertForm.amount} onChange={e => setConvertForm(f => ({ ...f, amount: e.target.value }))} className="bg-canvas border-divider text-sm" />
              </div>
              <Button className="w-full bg-gold text-black hover:bg-gold/90" onClick={handleConvert} disabled={converting}>
                {converting ? 'Converting...' : 'Convert'}
              </Button>
              {convertResult && (
                <div className="bg-canvas rounded-lg p-4 text-center">
                  <div className="font-mono text-2xl text-gold">
                    {convertResult.converted_amount?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 8 })} {convertResult.to_currency}
                  </div>
                  <div className="font-sans text-xs text-text-secondary mt-1">
                    Rate: {convertResult.rate} ({convertResult.rate_date})
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Rates Table */}
          <div className="lg:col-span-2">
            <Card className="bg-surface border-divider">
              <CardHeader>
                <CardTitle className="font-sans text-sm font-medium text-text-primary">
                  Exchange Rates ({rates.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="text-text-secondary text-sm">Loading rates...</div>
                ) : rates.length === 0 ? (
                  <p className="text-text-secondary text-sm text-center py-8">No exchange rates configured.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[500px]">
                      <thead>
                        <tr className="border-b border-divider">
                          {['Currency Pair', 'Rate', 'Date', 'Source'].map(h => (
                            <th key={h} className="font-mono text-[11px] uppercase text-text-secondary text-left px-4 py-3">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {rates.slice(0, 50).map(r => (
                          <tr key={r.id} className="border-t border-divider hover:bg-surface-hover/50 transition-colors">
                            <td className="font-mono text-sm text-text-primary px-4 py-3">
                              {r.from_currency} → {r.to_currency}
                            </td>
                            <td className="font-mono text-sm text-gold px-4 py-3">{r.rate}</td>
                            <td className="font-mono text-xs text-text-secondary px-4 py-3">{r.rate_date}</td>
                            <td className="px-4 py-3">
                              <Badge variant="outline" className="text-xs border-text-secondary/30 text-text-secondary">{r.source}</Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Add Rate Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="bg-surface border-divider text-text-primary">
          <DialogHeader>
            <DialogTitle className="font-sans text-sm">Add Exchange Rate</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="font-sans text-xs text-text-secondary">From Currency</Label>
                <Select value={addForm.from_currency} onValueChange={v => setAddForm(f => ({ ...f, from_currency: v }))}>
                  <SelectTrigger className="bg-canvas border-divider text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {CURRENCIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="font-sans text-xs text-text-secondary">To Currency</Label>
                <Select value={addForm.to_currency} onValueChange={v => setAddForm(f => ({ ...f, to_currency: v }))}>
                  <SelectTrigger className="bg-canvas border-divider text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {CURRENCIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label className="font-sans text-xs text-text-secondary">Rate</Label>
              <Input type="number" step="0.00000001" value={addForm.rate} onChange={e => setAddForm(f => ({ ...f, rate: e.target.value }))} placeholder="e.g. 0.85" className="bg-canvas border-divider text-sm" />
            </div>
            <div>
              <Label className="font-sans text-xs text-text-secondary">Date</Label>
              <Input type="date" value={addForm.rate_date} onChange={e => setAddForm(f => ({ ...f, rate_date: e.target.value }))} className="bg-canvas border-divider text-sm" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button onClick={handleAdd} className="bg-gold text-black hover:bg-gold/90">Add Rate</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Import Dialog */}
      <Dialog open={bulkOpen} onOpenChange={setBulkOpen}>
        <DialogContent className="bg-surface border-divider text-text-primary">
          <DialogHeader>
            <DialogTitle className="font-sans text-sm">Bulk Import Rates</DialogTitle>
          </DialogHeader>
          <div className="py-2">
            <Label className="font-sans text-xs text-text-secondary mb-1 block">JSON Array</Label>
            <textarea
              value={bulkText}
              onChange={e => setBulkText(e.target.value)}
              rows={8}
              placeholder={`[\n  { "from_currency": "USD", "to_currency": "EUR", "rate": 0.85, "rate_date": "2026-01-01", "source": "ecb" }\n]`}
              className="w-full bg-canvas border border-divider rounded-lg p-3 font-mono text-xs text-text-primary resize-none"
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setBulkOpen(false)}>Cancel</Button>
            <Button onClick={handleBulkImport} disabled={bulkLoading}>
              {bulkLoading ? 'Importing...' : 'Import'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
