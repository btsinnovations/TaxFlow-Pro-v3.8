import { useEffect, useState, useRef, useCallback } from 'react';
import {
  BookOpen, Plus, Trash2, Send, AlertCircle, CheckCircle, XCircle,
  AlertTriangle,
} from 'lucide-react';
import {
  getJournalEntries, createJournalEntry, deleteJournalEntry, postJournalEntry,
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
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface JournalLine {
  account_code: string;
  account_name: string;
  debit: number;
  credit: number;
  memo?: string;
}

interface JournalEntry {
  id: number;
  entry_number: string;
  entry_date: string;
  memo: string;
  source: string;
  tenant_id: number;
  user_id: number;
  lines: JournalLine[];
  created_at?: string;
}

export default function JournalEntriesPage() {
  const { selectedClient } = useClient();
  const { toast } = useToast();
  const sectionRef = useRef<HTMLDivElement>(null);

  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [postedOnly, setPostedOnly] = useState(false);

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    entry_number: `JE-${Date.now().toString().slice(-6)}`,
    entry_date: new Date().toISOString().slice(0, 10),
    memo: '',
    source: 'manual',
    lines: [] as JournalLine[],
  });

  // Posting
  const [posting, setPosting] = useState<number | null>(null);

  const fetchData = useCallback(async () => {
    if (!selectedClient) return;
    setLoading(true);
    try {
      const data = await getJournalEntries(selectedClient.id, 0, 100, postedOnly);
      setEntries(data);
    } catch {
      setError('Failed to load journal entries');
    } finally {
      setLoading(false);
    }
  }, [selectedClient, postedOnly]);

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
  }, [loading, entries]);

  const formatCurrency = (v: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Math.abs(v));

  const isBalanced = (lines: JournalLine[]) => {
    const totalDebits = lines.reduce((s, l) => s + l.debit, 0);
    const totalCredits = lines.reduce((s, l) => s + l.credit, 0);
    return Math.abs(totalDebits - totalCredits) < 0.01 && totalDebits > 0;
  };

  const addLine = () => {
    setCreateForm(f => ({
      ...f,
      lines: [...f.lines, { account_code: '', account_name: '', debit: 0, credit: 0 }],
    }));
  };

  const updateLine = (idx: number, field: keyof JournalLine, value: string | number) => {
    setCreateForm(f => ({
      ...f,
      lines: f.lines.map((l, i) => i === idx ? { ...l, [field]: value } : l),
    }));
  };

  const removeLine = (idx: number) => {
    setCreateForm(f => ({ ...f, lines: f.lines.filter((_, i) => i !== idx) }));
  };

  const handleCreate = async () => {
    if (!selectedClient || createForm.lines.length < 2) {
      toast({ title: 'Invalid entry', description: 'At least 2 line items required.', variant: 'destructive' });
      return;
    }
    if (!isBalanced(createForm.lines)) {
      toast({ title: 'Unbalanced', description: 'Total debits must equal total credits.', variant: 'destructive' });
      return;
    }
    try {
      await createJournalEntry(selectedClient.id, {
        entry_number: createForm.entry_number,
        entry_date: createForm.entry_date,
        memo: createForm.memo,
        source: createForm.source,
        lines: createForm.lines,
      });
      toast({ title: 'Journal entry created', description: createForm.entry_number });
      setCreateOpen(false);
      setCreateForm({ entry_number: `JE-${Date.now().toString().slice(-6)}`, entry_date: new Date().toISOString().slice(0, 10), memo: '', source: 'manual', lines: [] });
      fetchData();
    } catch (e: any) {
      toast({ title: 'Create failed', description: e.message, variant: 'destructive' });
    }
  };

  const handlePost = async (jeId: number) => {
    setPosting(jeId);
    try {
      await postJournalEntry(jeId);
      toast({ title: 'Entry posted', description: `Journal entry #${jeId} posted to transactions` });
      fetchData();
    } catch (e: any) {
      toast({ title: 'Post failed', description: e.message, variant: 'destructive' });
    } finally {
      setPosting(null);
    }
  };

  const handleDelete = async (jeId: number, entryNumber: string) => {
    if (!confirm(`Delete journal entry ${entryNumber}?`)) return;
    try {
      await deleteJournalEntry(jeId);
      toast({ title: 'Entry deleted', description: entryNumber });
      fetchData();
    } catch (e: any) {
      toast({ title: 'Delete failed', description: e.message, variant: 'destructive' });
    }
  };

  const totalDebits = (lines: JournalLine[]) => lines.reduce((s, l) => s + l.debit, 0);
  const totalCredits = (lines: JournalLine[]) => lines.reduce((s, l) => s + l.credit, 0);

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
              <BookOpen className="text-gold" size={28} />
              Journal Entries
            </h1>
            <p className="font-sans text-sm text-text-secondary mt-1">
              Create double-entry journal entries and post them to transactions.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
              <input
                type="checkbox"
                checked={postedOnly}
                onChange={e => setPostedOnly(e.target.checked)}
                className="rounded border-divider"
              />
              Posted only
            </label>
            <Button onClick={() => setCreateOpen(true)} className="bg-gold text-black hover:bg-gold/90">
              <Plus size={16} className="mr-1" /> New Entry
            </Button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20 mb-6">
            <AlertCircle size={16} />{error}
          </div>
        )}

        {loading ? (
          <div className="text-text-secondary text-sm">Loading journal entries...</div>
        ) : entries.length === 0 ? (
          <Card className="bg-surface border-divider">
            <CardContent className="p-8 text-center">
              <BookOpen size={32} className="text-text-secondary mx-auto mb-3" />
              <p className="text-text-secondary font-sans text-sm mb-4">No journal entries yet.</p>
              <Button onClick={() => setCreateOpen(true)} className="bg-gold text-black hover:bg-gold/90">
                <Plus size={16} className="mr-1" /> Create First Entry
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {entries.map(entry => {
              const balanced = isBalanced(entry.lines);
              const total = totalDebits(entry.lines);
              const isPosted = entry.lines.some(l => l.debit === 0 && l.credit === 0);
              return (
                <Card key={entry.id} className="bg-surface border-divider">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono text-sm text-gold">{entry.entry_number}</span>
                          <span className="font-mono text-xs text-text-secondary">{entry.entry_date}</span>
                          <Badge variant="outline" className="text-xs border-text-secondary/30 text-text-secondary">{entry.source}</Badge>
                          <Badge variant="outline" className={`text-xs ${entry.id <= 0 || false ? 'border-emerald-400/30 text-emerald-400' : 'border-amber-400/30 text-amber-400'}`}>
                            Unposted
                          </Badge>
                        </div>
                        {entry.memo && <p className="font-sans text-xs text-text-secondary">{entry.memo}</p>}
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" className="text-xs border-emerald-400/30 text-emerald-400 hover:bg-emerald-400/10" onClick={() => handlePost(entry.id)} disabled={posting === entry.id}>
                          <Send size={12} className="mr-1" /> {posting === entry.id ? 'Posting...' : 'Post'}
                        </Button>
                        <Button size="sm" variant="outline" className="text-xs text-red-400 border-red-400/30 hover:bg-red-400/10" onClick={() => handleDelete(entry.id, entry.entry_number)}>
                          <Trash2 size={12} />
                        </Button>
                      </div>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[400px]">
                        <thead>
                          <tr className="border-b border-divider">
                            {['Account Code', 'Account Name', 'Debit', 'Credit'].map(h => (
                              <th key={h} className="font-mono text-[11px] uppercase text-text-secondary text-left px-3 py-2">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {entry.lines.map((line, i) => (
                            <tr key={i} className="border-t border-divider">
                              <td className="font-mono text-xs text-text-primary px-3 py-2">{line.account_code}</td>
                              <td className="font-sans text-xs text-text-secondary px-3 py-2">{line.account_name}</td>
                              <td className="font-mono text-xs text-emerald-400 px-3 py-2">{line.debit > 0 ? formatCurrency(line.debit) : ''}</td>
                              <td className="font-mono text-xs text-red-400 px-3 py-2">{line.credit > 0 ? formatCurrency(line.credit) : ''}</td>
                            </tr>
                          ))}
                        </tbody>
                        <tfoot>
                          <tr className="border-t border-divider font-medium">
                            <td colSpan={2} className="font-sans text-xs text-text-primary px-3 py-2">Totals</td>
                            <td className={`font-mono text-xs px-3 py-2 ${balanced ? 'text-emerald-400' : 'text-red-400'}`}>
                              {formatCurrency(total)}
                            </td>
                            <td className={`font-mono text-xs px-3 py-2 ${balanced ? 'text-emerald-400' : 'text-red-400'}`}>
                              {formatCurrency(total)}
                            </td>
                          </tr>
                        </tfoot>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Create Entry Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-surface border-divider text-text-primary max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-sans text-sm">New Journal Entry</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label className="font-sans text-xs text-text-secondary">Entry Number</Label>
                <Input value={createForm.entry_number} onChange={e => setCreateForm(f => ({ ...f, entry_number: e.target.value }))} className="bg-canvas border-divider text-sm" />
              </div>
              <div>
                <Label className="font-sans text-xs text-text-secondary">Date</Label>
                <Input type="date" value={createForm.entry_date} onChange={e => setCreateForm(f => ({ ...f, entry_date: e.target.value }))} className="bg-canvas border-divider text-sm" />
              </div>
              <div>
                <Label className="font-sans text-xs text-text-secondary">Source</Label>
                <Input value={createForm.source} onChange={e => setCreateForm(f => ({ ...f, source: e.target.value }))} className="bg-canvas border-divider text-sm" />
              </div>
            </div>
            <div>
              <Label className="font-sans text-xs text-text-secondary">Memo</Label>
              <Input value={createForm.memo} onChange={e => setCreateForm(f => ({ ...f, memo: e.target.value }))} placeholder="Description of this journal entry" className="bg-canvas border-divider text-sm" />
            </div>

            {/* Lines */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label className="font-sans text-xs text-text-secondary">Line Items</Label>
                <Button size="sm" variant="ghost" onClick={addLine} className="h-6 text-xs">
                  <Plus size={12} className="mr-1" /> Add Line
                </Button>
              </div>
              <div className="space-y-2">
                {createForm.lines.map((line, idx) => (
                  <div key={idx} className="grid grid-cols-12 gap-2 items-end">
                    <div className="col-span-2">
                      <Input value={line.account_code} onChange={e => updateLine(idx, 'account_code', e.target.value)} placeholder="Code" className="bg-canvas border-divider text-xs h-7" />
                    </div>
                    <div className="col-span-3">
                      <Input value={line.account_name} onChange={e => updateLine(idx, 'account_name', e.target.value)} placeholder="Account name" className="bg-canvas border-divider text-xs h-7" />
                    </div>
                    <div className="col-span-2">
                      <Input type="number" step="0.01" value={line.debit || ''} onChange={e => updateLine(idx, 'debit', parseFloat(e.target.value) || 0)} placeholder="Debit" className="bg-canvas border-divider text-xs h-7" />
                    </div>
                    <div className="col-span-2">
                      <Input type="number" step="0.01" value={line.credit || ''} onChange={e => updateLine(idx, 'credit', parseFloat(e.target.value) || 0)} placeholder="Credit" className="bg-canvas border-divider text-xs h-7" />
                    </div>
                    <div className="col-span-2">
                      <Input value={line.memo || ''} onChange={e => updateLine(idx, 'memo', e.target.value)} placeholder="Memo" className="bg-canvas border-divider text-xs h-7" />
                    </div>
                    <div className="col-span-1">
                      <Button size="icon" variant="ghost" className="h-7 w-7 text-red-400" onClick={() => removeLine(idx)}>
                        <XCircle size={14} />
                      </Button>
                    </div>
                  </div>
                ))}
                {createForm.lines.length === 0 && (
                  <p className="text-center text-text-secondary text-xs py-4">Add at least 2 line items with balanced debits and credits.</p>
                )}
              </div>
            </div>

            {/* Balance indicator */}
            {createForm.lines.length > 0 && (
              <div className={`rounded-lg p-3 flex items-center justify-between ${isBalanced(createForm.lines) ? 'bg-emerald-400/10 border border-emerald-400/20' : 'bg-red-400/10 border border-red-400/20'}`}>
                <div className="flex items-center gap-2">
                  {isBalanced(createForm.lines) ? <CheckCircle size={14} className="text-emerald-400" /> : <XCircle size={14} className="text-red-400" />}
                  <span className={`font-sans text-xs ${isBalanced(createForm.lines) ? 'text-emerald-400' : 'text-red-400'}`}>
                    {isBalanced(createForm.lines) ? 'Balanced' : 'Unbalanced'}
                  </span>
                </div>
                <span className="font-mono text-xs text-text-secondary">
                  Debits: {formatCurrency(totalDebits(createForm.lines))} | Credits: {formatCurrency(totalCredits(createForm.lines))}
                </span>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} className="bg-gold text-black hover:bg-gold/90" disabled={!isBalanced(createForm.lines) || createForm.lines.length < 2}>
              Create Entry
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
