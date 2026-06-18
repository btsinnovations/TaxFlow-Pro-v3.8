import { useEffect, useState, useRef, useCallback } from 'react';
import {
  Wallet, Plus, Trash2, Eye, AlertCircle, X,
} from 'lucide-react';
import {
  getBudgets, createBudget, deleteBudget, getBudgetVsActual, getCategories,
} from '@/hooks/useAPI';
import { useClient } from '@/context/ClientContext';
import { useToast } from '@/hooks/useToast';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
} from '@/components/ui/chart';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from 'recharts';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface Budget {
  id: number;
  name: string;
  period_start: string;
  period_end: string;
  total_budget: number;
  is_active: boolean;
  created_at: string;
}

interface BudgetEntry {
  id: number;
  category: string;
  amount: number;
}

interface BudgetDetail extends Budget {
  entries: BudgetEntry[];
}

interface VsActualEntry {
  category: string;
  budgeted: number;
  actual: number;
  variance: number;
  variance_pct: number | null;
}

interface VsActualData {
  entries: VsActualEntry[];
  total_budgeted: number;
  total_actual: number;
  total_variance: number;
}

export default function BudgetsPage() {
  const { selectedClient } = useClient();
  const { toast } = useToast();
  const sectionRef = useRef<HTMLDivElement>(null);

  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: '',
    period_start: '',
    period_end: '',
    entries: [] as { category: string; amount: number }[],
  });

  // Detail view
  const [selectedBudget, setSelectedBudget] = useState<BudgetDetail | null>(null);
  const [vsActual, setVsActual] = useState<VsActualData | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Categories
  const [categories, setCategories] = useState<string[]>([]);

  const fetchData = useCallback(async () => {
    if (!selectedClient) { setLoading(false); return; }
    setLoading(true);
    setError('');
    try {
      const data = await getBudgets(selectedClient.id);
      setBudgets(data);
    } catch {
      setError('Failed to load budgets');
    } finally {
      setLoading(false);
    }
  }, [selectedClient]);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    getCategories().then(cats => setCategories(cats.map((c: any) => c.id || c.name).filter(Boolean))).catch(() => {});
  }, []);

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
  }, [loading, budgets]);

  const formatCurrency = (v: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Math.abs(v));

  const loadBudgetDetail = async (budget: Budget) => {
    setDetailLoading(true);
    try {
      const [detail, vsa] = await Promise.all([
        (await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'}/budgets/${budget.id}`, {
          headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
        })).json(),
        getBudgetVsActual(budget.id),
      ]);
      setSelectedBudget(detail);
      setVsActual(vsa);
    } catch (e: any) {
      toast({ title: 'Failed to load budget details', description: e.message, variant: 'destructive' });
    } finally {
      setDetailLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!selectedClient || !createForm.name || !createForm.period_start || !createForm.period_end) {
      toast({ title: 'Missing fields', description: 'Name, start date, and end date are required.', variant: 'destructive' });
      return;
    }
    try {
      await createBudget(selectedClient.id, {
        name: createForm.name,
        period_start: createForm.period_start,
        period_end: createForm.period_end,
        is_active: true,
        entries: createForm.entries.filter(e => e.amount > 0),
      });
      toast({ title: 'Budget created', description: `${createForm.name} has been created.` });
      setCreateOpen(false);
      setCreateForm({ name: '', period_start: '', period_end: '', entries: [] });
      fetchData();
    } catch (e: any) {
      toast({ title: 'Create failed', description: e.message, variant: 'destructive' });
    }
  };

  const addEntryRow = () => {
    setCreateForm(f => ({
      ...f,
      entries: [...f.entries, { category: '', amount: 0 }],
    }));
  };

  const updateEntry = (idx: number, field: 'category' | 'amount', value: string | number) => {
    setCreateForm(f => ({
      ...f,
      entries: f.entries.map((e, i) => i === idx ? { ...e, [field]: value } : e),
    }));
  };

  const removeEntry = (idx: number) => {
    setCreateForm(f => ({ ...f, entries: f.entries.filter((_, i) => i !== idx) }));
  };

  const handleDelete = async (budgetId: number, name: string) => {
    if (!confirm(`Delete budget "${name}"? This cannot be undone.`)) return;
    try {
      await deleteBudget(budgetId);
      toast({ title: 'Budget deleted', description: `"${name}" has been deleted.` });
      if (selectedBudget?.id === budgetId) {
        setSelectedBudget(null);
        setVsActual(null);
      }
      fetchData();
    } catch (e: any) {
      toast({ title: 'Delete failed', description: e.message, variant: 'destructive' });
    }
  };

  const chartConfig = {
    budgeted: { label: 'Budgeted', color: '#3b82f6' },
    actual: { label: 'Actual', color: '#f59e0b' },
  };

  const chartData = vsActual
    ? vsActual.entries.slice(0, 12).map(e => ({
        category: e.category,
        budgeted: e.budgeted,
        actual: e.actual,
      }))
    : [];

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
              <Wallet className="text-gold" size={28} />
              Budgets
            </h1>
            <p className="font-sans text-sm text-text-secondary mt-1">
              Create and track budgets against actual spending.
            </p>
          </div>
          <Button onClick={() => setCreateOpen(true)} className="bg-gold text-black hover:bg-gold/90">
            <Plus size={16} className="mr-1" /> New Budget
          </Button>
        </div>

        {loading ? (
          <div className="text-text-secondary font-sans text-sm">Loading budgets...</div>
        ) : error ? (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20">
            <AlertCircle size={16} />{error}
          </div>
        ) : budgets.length === 0 ? (
          <div className="bg-surface border border-divider rounded-lg p-8 text-center">
            <Wallet size={32} className="text-text-secondary mx-auto mb-3" />
            <p className="text-text-secondary font-sans text-sm mb-4">No budgets created yet.</p>
            <Button onClick={() => setCreateOpen(true)} className="bg-gold text-black hover:bg-gold/90">
              <Plus size={16} className="mr-1" /> Create Your First Budget
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {budgets.map(b => (
              <Card key={b.id} className="bg-surface border-divider">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <CardTitle className="font-sans text-sm font-medium text-text-primary">{b.name}</CardTitle>
                    <Badge variant="outline" className={`text-xs ${b.is_active ? 'border-emerald-400/30 text-emerald-400' : 'border-text-secondary/30 text-text-secondary'}`}>
                      {b.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="font-mono text-xl text-gold mb-2">{formatCurrency(b.total_budget)}</div>
                  <div className="font-sans text-xs text-text-secondary mb-4">
                    {b.period_start} → {b.period_end}
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" className="flex-1 text-xs" onClick={() => loadBudgetDetail(b)}>
                      <Eye size={12} className="mr-1" /> Details
                    </Button>
                    <Button size="sm" variant="outline" className="text-red-400 border-red-400/30 hover:bg-red-400/10" onClick={() => handleDelete(b.id, b.name)}>
                      <Trash2 size={12} />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Budget Detail View */}
        {selectedBudget && vsActual && (
          <Card className="bg-surface border-divider mt-8">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="font-sans text-sm font-medium text-text-primary">
                  {selectedBudget.name} — Budget vs Actual
                </CardTitle>
                <Button size="sm" variant="ghost" onClick={() => { setSelectedBudget(null); setVsActual(null); }}>
                  <X size={14} />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {detailLoading ? (
                <div className="text-text-secondary text-sm">Loading details...</div>
              ) : (
                <>
                  {/* Summary */}
                  <div className="grid grid-cols-3 gap-4 mb-6">
                    <div className="bg-canvas rounded-lg p-3">
                      <div className="font-sans text-[10px] uppercase tracking-wide text-text-secondary">Total Budgeted</div>
                      <div className="font-mono text-lg text-blue-400">{formatCurrency(vsActual.total_budgeted)}</div>
                    </div>
                    <div className="bg-canvas rounded-lg p-3">
                      <div className="font-sans text-[10px] uppercase tracking-wide text-text-secondary">Total Actual</div>
                      <div className="font-mono text-lg text-amber-400">{formatCurrency(vsActual.total_actual)}</div>
                    </div>
                    <div className="bg-canvas rounded-lg p-3">
                      <div className="font-sans text-[10px] uppercase tracking-wide text-text-secondary">Variance</div>
                      <div className={`font-mono text-lg ${vsActual.total_variance >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {vsActual.total_variance >= 0 ? '+' : '-'}{formatCurrency(vsActual.total_variance)}
                      </div>
                    </div>
                  </div>

                  {/* Chart */}
                  {chartData.length > 0 && (
                    <ChartContainer config={chartConfig} className="h-[300px] mb-6">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-divider)" />
                          <XAxis dataKey="category" tick={{ fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} />
                          <ChartTooltip content={<ChartTooltipContent formatter={(v: any) => formatCurrency(Number(v))} />} />
                          <ChartLegend content={<ChartLegendContent />} />
                          <Bar dataKey="budgeted" fill="var(--color-budgeted)" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="actual" fill="var(--color-actual)" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartContainer>
                  )}

                  {/* Category-wise table with progress bars */}
                  <div className="space-y-3">
                    {vsActual.entries.map(e => {
                      const pct = e.budgeted > 0 ? Math.min((e.actual / e.budgeted) * 100, 100) : 0;
                      const overBudget = e.actual > e.budgeted && e.budgeted > 0;
                      return (
                        <div key={e.category} className="bg-canvas rounded-lg p-4">
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-sans text-sm text-text-primary capitalize">{e.category}</span>
                            <div className="flex items-center gap-4 text-xs font-mono">
                              <span className="text-blue-400">{formatCurrency(e.budgeted)}</span>
                              <span className="text-amber-400">{formatCurrency(e.actual)}</span>
                              <span className={overBudget ? 'text-red-400' : 'text-emerald-400'}>
                                {e.variance >= 0 ? '+' : ''}{formatCurrency(e.variance)}
                                {e.variance_pct !== null && ` (${e.variance_pct >= 0 ? '+' : ''}${e.variance_pct}%)`}
                              </span>
                            </div>
                          </div>
                          <Progress
                            value={pct}
                            className={`h-2 ${overBudget ? '[&>div]:bg-red-400' : '[&>div]:bg-emerald-400'}`}
                          />
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Create Budget Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-surface border-divider text-text-primary max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-sans text-sm">Create Budget</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <label className="font-sans text-xs text-text-secondary mb-1 block">Budget Name</label>
              <Input
                value={createForm.name}
                onChange={e => setCreateForm(f => ({ ...f, name: e.target.value }))}
                placeholder="e.g. Q1 2026 Operating Budget"
                className="bg-canvas border-divider text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="font-sans text-xs text-text-secondary mb-1 block">Period Start</label>
                <Input
                  type="date"
                  value={createForm.period_start}
                  onChange={e => setCreateForm(f => ({ ...f, period_start: e.target.value }))}
                  className="bg-canvas border-divider text-sm"
                />
              </div>
              <div>
                <label className="font-sans text-xs text-text-secondary mb-1 block">Period End</label>
                <Input
                  type="date"
                  value={createForm.period_end}
                  onChange={e => setCreateForm(f => ({ ...f, period_end: e.target.value }))}
                  className="bg-canvas border-divider text-sm"
                />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="font-sans text-xs text-text-secondary">Budget Entries</label>
                <Button size="sm" variant="ghost" onClick={addEntryRow} className="h-6 text-xs">
                  <Plus size={12} className="mr-1" /> Add Category
                </Button>
              </div>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {createForm.entries.map((entry, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <Select value={entry.category} onValueChange={v => updateEntry(idx, 'category', v)}>
                      <SelectTrigger className="flex-1 bg-canvas border-divider text-xs h-8">
                        <SelectValue placeholder="Category" />
                      </SelectTrigger>
                      <SelectContent>
                        {categories.map(cat => <SelectItem key={cat} value={cat}>{cat}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <Input
                      type="number"
                      step="0.01"
                      value={entry.amount || ''}
                      onChange={e => updateEntry(idx, 'amount', parseFloat(e.target.value) || 0)}
                      placeholder="Amount"
                      className="w-28 bg-canvas border-divider text-xs h-8"
                    />
                    <Button size="icon" variant="ghost" className="h-8 w-8 text-red-400" onClick={() => removeEntry(idx)}>
                      <X size={14} />
                    </Button>
                  </div>
                ))}
                {createForm.entries.length === 0 && (
                  <div className="text-center text-text-secondary text-xs py-4">
                    Add categories and amounts for this budget.
                  </div>
                )}
              </div>
              {createForm.entries.length > 0 && (
                <div className="text-right font-mono text-sm text-gold mt-2">
                  Total: {formatCurrency(createForm.entries.reduce((s, e) => s + e.amount, 0))}
                </div>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} className="bg-gold text-black hover:bg-gold/90">Create Budget</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
