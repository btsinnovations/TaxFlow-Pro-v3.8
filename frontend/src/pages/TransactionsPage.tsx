import { useEffect, useState, useRef, useCallback } from 'react';
import {
  ArrowLeftRight, Search, Pencil, Check, X,
  AlertCircle, Archive, FileText, Tag, RefreshCw,
} from 'lucide-react';
import {
  getTransactions, getTransactionsSummary, updateTransaction,
  archiveTransaction, getCategories,
} from '@/hooks/useAPI';
import { useClient } from '@/context/ClientContext';
import { useToast } from '@/hooks/useToast';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Pagination, PaginationContent, PaginationItem, PaginationLink,
  PaginationNext, PaginationPrevious,
} from '@/components/ui/pagination';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface Transaction {
  id: number;
  date: string;
  description: string;
  amount: number;
  tx_type: 'credit' | 'debit';
  category?: string;
  confirmed: boolean;
  archived: boolean;
  is_manual: boolean;
  is_journal: boolean;
  tax_line?: string;
  created_at?: string;
}

interface TxSummary {
  total_count: number;
  debit_total: number;
  credit_total: number;
  net_total: number;
  confirmed_count: number;
  unconfirmed_count: number;
  categories: { category: string; count: number; total: number }[];
  monthly: { month: string; count: number; total: number }[];
}

const PAGE_SIZE = 25;

export default function TransactionsPage() {
  const { selectedClient } = useClient();
  const { toast } = useToast();
  const sectionRef = useRef<HTMLDivElement>(null);

  // Filters
  const [search, setSearch] = useState('');
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [categoryFilter, setCategoryFilter] = useState('');
  const [txTypeFilter, setTxTypeFilter] = useState('');
  const [confirmedFilter, setConfirmedFilter] = useState('');
  const [showArchived, setShowArchived] = useState(false);

  // Data
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [summary, setSummary] = useState<TxSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [page, setPage] = useState(0);

  // Categories for dropdown
  const [categories, setCategories] = useState<string[]>([]);

  // Inline editing
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Partial<Transaction>>({});

  // Bulk selection
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Category edit dialog
  const [categoryDialogOpen, setCategoryDialogOpen] = useState(false);
  const [categoryDialogTx, setCategoryDialogTx] = useState<Transaction | null>(null);
  const [categoryDialogValue, setCategoryDialogValue] = useState('');

  const fetchData = useCallback(async () => {
    if (!selectedClient) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const [txs, sum, cats] = await Promise.all([
        getTransactions({
          client_id: selectedClient.id,
          year: year || undefined,
          category: categoryFilter || undefined,
          search: search || undefined,
          tx_type: txTypeFilter || undefined,
          confirmed: confirmedFilter === 'true' ? true : confirmedFilter === 'false' ? false : undefined,
          archived: showArchived,
          skip: page * PAGE_SIZE,
          limit: PAGE_SIZE,
          order_by: 'date',
          order_dir: 'desc',
        }),
        getTransactionsSummary({
          client_id: selectedClient.id,
          year: year || undefined,
          category: categoryFilter || undefined,
        }),
        getCategories().catch(() => []),
      ]);
      setTransactions(txs);
      setSummary(sum);
      setCategories(cats.map((c: any) => c.id || c.name).filter(Boolean));
    } catch {
      setError('Failed to load transactions');
    } finally {
      setLoading(false);
    }
  }, [selectedClient, year, categoryFilter, search, txTypeFilter, confirmedFilter, showArchived, page]);

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
  }, [loading, transactions]);

  const formatCurrency = (v: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Math.abs(v));

  const handleEdit = (tx: Transaction) => {
    setEditingId(tx.id);
    setEditForm({ ...tx });
  };

  const handleSave = async () => {
    if (!editingId) return;
    try {
      const { id, ...updates } = editForm;
      await updateTransaction(editingId, updates);
      toast({ title: 'Transaction updated', description: `Transaction #${editingId} saved.` });
      setEditingId(null);
      fetchData();
    } catch (e: any) {
      toast({ title: 'Update failed', description: e.message, variant: 'destructive' });
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditForm({});
  };

  const handleArchive = async (txId: number) => {
    try {
      await archiveTransaction(txId);
      toast({ title: 'Transaction archived', description: `Transaction #${txId} has been archived.` });
      fetchData();
    } catch (e: any) {
      toast({ title: 'Archive failed', description: e.message, variant: 'destructive' });
    }
  };

  const handleCategoryAssign = async () => {
    if (!categoryDialogTx || !categoryDialogValue) return;
    try {
      await updateTransaction(categoryDialogTx.id, { category: categoryDialogValue });
      toast({ title: 'Category assigned', description: `Transaction #${categoryDialogTx.id} → ${categoryDialogValue}` });
      setCategoryDialogOpen(false);
      fetchData();
    } catch (e: any) {
      toast({ title: 'Failed', description: e.message, variant: 'destructive' });
    }
  };

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === transactions.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(transactions.map(t => t.id)));
    }
  };

  const handleBulkArchive = async () => {
    if (selectedIds.size === 0) return;
    try {
      await Promise.all([...selectedIds].map(id => archiveTransaction(id)));
      toast({ title: 'Archived', description: `${selectedIds.size} transaction(s) archived.` });
      setSelectedIds(new Set());
      fetchData();
    } catch (e: any) {
      toast({ title: 'Bulk archive failed', description: e.message, variant: 'destructive' });
    }
  };

  const totalPages = summary ? Math.ceil(summary.total_count / PAGE_SIZE) : 0;

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
            <ArrowLeftRight className="text-gold" size={28} />
            Transactions
          </h1>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Search, filter, edit, and manage all transactions.
          </p>
        </div>

        {/* Summary Cards */}
        {summary && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
            {[
              { label: 'Total', value: summary.total_count.toLocaleString(), color: 'text-text-primary' },
              { label: 'Confirmed', value: summary.confirmed_count.toLocaleString(), color: 'text-emerald-400' },
              { label: 'Unconfirmed', value: summary.unconfirmed_count.toLocaleString(), color: 'text-amber-400' },
              { label: 'Income', value: formatCurrency(summary.credit_total), color: 'text-emerald-400' },
              { label: 'Expenses', value: formatCurrency(summary.debit_total), color: 'text-red-400' },
              { label: 'Net', value: formatCurrency(summary.net_total), color: summary.net_total >= 0 ? 'text-blue-400' : 'text-red-400' },
            ].map(s => (
              <div key={s.label} className="bg-surface border border-divider rounded-lg p-3">
                <div className="font-sans text-[10px] uppercase tracking-wide text-text-secondary">{s.label}</div>
                <div className={`font-mono text-lg ${s.color}`}>{s.value}</div>
              </div>
            ))}
          </div>
        )}

        {/* Filters */}
        <div className="bg-surface border border-divider rounded-lg p-4 mb-4">
          <div className="flex flex-wrap gap-3 items-center">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
                <Input
                  placeholder="Search description or category..."
                  value={search}
                  onChange={e => { setSearch(e.target.value); setPage(0); }}
                  className="pl-9 bg-canvas border-divider text-sm"
                />
              </div>
            </div>
            <Select value={year} onValueChange={(v) => { setYear(v); setPage(0); }}>
              <SelectTrigger className="w-[120px] bg-canvas border-divider text-sm">
                <SelectValue placeholder="Year" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Years</SelectItem>
                {Array.from({ length: 6 }, (_, i) => new Date().getFullYear() - i).map(y => (
                  <SelectItem key={y} value={String(y)}>{y}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={txTypeFilter} onValueChange={(v) => { setTxTypeFilter(v); setPage(0); }}>
              <SelectTrigger className="w-[130px] bg-canvas border-divider text-sm">
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Types</SelectItem>
                <SelectItem value="credit">Income</SelectItem>
                <SelectItem value="debit">Expense</SelectItem>
              </SelectContent>
            </Select>
            <Select value={confirmedFilter} onValueChange={(v) => { setConfirmedFilter(v); setPage(0); }}>
              <SelectTrigger className="w-[130px] bg-canvas border-divider text-sm">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All</SelectItem>
                <SelectItem value="true">Confirmed</SelectItem>
                <SelectItem value="false">Unconfirmed</SelectItem>
              </SelectContent>
            </Select>
            <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
              <input
                type="checkbox"
                checked={showArchived}
                onChange={e => { setShowArchived(e.target.checked); setPage(0); }}
                className="rounded border-divider"
              />
              Archived
            </label>
            <Button size="sm" variant="ghost" onClick={() => {
              setSearch(''); setYear(String(new Date().getFullYear()));
              setCategoryFilter(''); setTxTypeFilter('');
              setConfirmedFilter(''); setShowArchived(false); setPage(0);
            }}>
              <RefreshCw size={14} /> Reset
            </Button>
          </div>
        </div>

        {/* Bulk Actions Bar */}
        {selectedIds.size > 0 && (
          <div className="flex items-center gap-3 mb-3 p-3 bg-gold/10 border border-gold/20 rounded-lg">
            <span className="font-sans text-sm text-gold">{selectedIds.size} selected</span>
            <Button size="sm" variant="outline" className="border-gold/30 text-gold hover:bg-gold/10" onClick={handleBulkArchive}>
              <Archive size={14} /> Archive Selected
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setSelectedIds(new Set())}>Clear</Button>
          </div>
        )}

        {/* Table */}
        {!selectedClient ? (
          <div className="bg-surface border border-divider rounded-lg p-8 text-center">
            <FileText size={32} className="text-text-secondary mx-auto mb-3" />
            <p className="text-text-secondary font-sans text-sm mb-4">Select a client to view transactions.</p>
          </div>
        ) : loading ? (
          <div className="text-text-secondary font-sans text-sm">Loading transactions...</div>
        ) : error ? (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20">
            <AlertCircle size={16} />
            {error}
          </div>
        ) : transactions.length === 0 ? (
          <div className="bg-surface border border-divider rounded-lg p-8 text-center">
            <FileText size={32} className="text-text-secondary mx-auto mb-3" />
            <p className="text-text-secondary font-sans text-sm">No transactions found.</p>
          </div>
        ) : (
          <div className="bg-surface border border-divider rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px]">
                <thead>
                  <tr className="bg-surface">
                    <th className="px-3 py-3 w-10">
                      <input
                        type="checkbox"
                        checked={selectedIds.size === transactions.length && transactions.length > 0}
                        onChange={toggleSelectAll}
                        className="rounded border-divider"
                      />
                    </th>
                    {['Date', 'Description', 'Amount', 'Type', 'Category', 'Status', 'Actions'].map(h => (
                      <th key={h} className="font-mono text-[11px] uppercase text-text-secondary text-left px-3 py-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((tx) => {
                    const isEditing = editingId === tx.id;
                    return (
                      <tr key={tx.id} className="border-t border-divider hover:bg-surface-hover/50 transition-colors duration-150">
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            checked={selectedIds.has(tx.id)}
                            onChange={() => toggleSelect(tx.id)}
                            className="rounded border-divider"
                            disabled={isEditing}
                          />
                        </td>
                        {/* Date */}
                        <td className="font-mono text-xs text-text-secondary px-3 py-2 whitespace-nowrap">
                          {isEditing ? (
                            <Input value={editForm.date || ''} onChange={e => setEditForm(f => ({ ...f, date: e.target.value }))} className="h-7 text-xs bg-canvas border-divider" />
                          ) : tx.date}
                        </td>
                        {/* Description */}
                        <td className="font-sans text-sm text-text-primary px-3 py-2 max-w-[300px]">
                          {isEditing ? (
                            <Input value={editForm.description || ''} onChange={e => setEditForm(f => ({ ...f, description: e.target.value }))} className="h-7 text-xs bg-canvas border-divider" />
                          ) : (
                            <span className="truncate block">{tx.description}</span>
                          )}
                        </td>
                        {/* Amount */}
                        <td className={`font-mono text-sm px-3 py-2 whitespace-nowrap ${tx.tx_type === 'credit' ? 'text-emerald-400' : 'text-red-400'}`}>
                          {isEditing ? (
                            <Input type="number" step="0.01" value={editForm.amount ?? ''} onChange={e => setEditForm(f => ({ ...f, amount: parseFloat(e.target.value) || 0 }))} className="h-7 text-xs bg-canvas border-divider" />
                          ) : (
                            `${tx.tx_type === 'debit' ? '-' : '+'}${formatCurrency(tx.amount)}`
                          )}
                        </td>
                        {/* Type */}
                        <td className="px-3 py-2">
                          {isEditing ? (
                            <Select value={editForm.tx_type || 'debit'} onValueChange={v => setEditForm(f => ({ ...f, tx_type: v as 'credit' | 'debit' }))}>
                              <SelectTrigger className="h-7 text-xs bg-canvas border-divider"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="credit">Income</SelectItem>
                                <SelectItem value="debit">Expense</SelectItem>
                              </SelectContent>
                            </Select>
                          ) : (
                            <Badge variant="outline" className={`text-xs ${tx.tx_type === 'credit' ? 'border-emerald-400/30 text-emerald-400' : 'border-red-400/30 text-red-400'}`}>
                              {tx.tx_type === 'credit' ? 'Income' : 'Expense'}
                            </Badge>
                          )}
                        </td>
                        {/* Category */}
                        <td className="px-3 py-2">
                          {isEditing ? (
                            <Select value={editForm.category || ''} onValueChange={v => setEditForm(f => ({ ...f, category: v }))}>
                              <SelectTrigger className="h-7 text-xs bg-canvas border-divider"><SelectValue placeholder="Select" /></SelectTrigger>
                              <SelectContent>
                                {categories.map(cat => (
                                  <SelectItem key={cat} value={cat}>{cat}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          ) : tx.category ? (
                            <Badge variant="outline" className="text-xs border-gold/30 text-gold">
                              <Tag size={10} className="mr-1" />
                              {tx.category}
                            </Badge>
                          ) : (
                            <Button size="sm" variant="ghost" className="h-6 text-xs text-text-secondary" onClick={() => {
                              setCategoryDialogTx(tx);
                              setCategoryDialogValue('');
                              setCategoryDialogOpen(true);
                            }}>
                              Assign
                            </Button>
                          )}
                        </td>
                        {/* Status */}
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-1">
                            <span className={`w-1.5 h-1.5 rounded-full ${tx.confirmed ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                            <span className="font-sans text-xs text-text-secondary">{tx.confirmed ? 'Confirmed' : 'Pending'}</span>
                            {tx.archived && <Badge variant="outline" className="text-xs ml-1 border-text-secondary/30 text-text-secondary">Archived</Badge>}
                            {tx.is_manual && <Badge variant="outline" className="text-xs ml-1 border-blue-400/30 text-blue-400">Manual</Badge>}
                          </div>
                        </td>
                        {/* Actions */}
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-1">
                            {isEditing ? (
                              <>
                                <Button size="icon" variant="ghost" className="h-7 w-7 text-emerald-400" onClick={handleSave}>
                                  <Check size={14} />
                                </Button>
                                <Button size="icon" variant="ghost" className="h-7 w-7 text-red-400" onClick={handleCancelEdit}>
                                  <X size={14} />
                                </Button>
                              </>
                            ) : (
                              <>
                                <Button size="icon" variant="ghost" className="h-7 w-7 text-gold" onClick={() => handleEdit(tx)}>
                                  <Pencil size={14} />
                                </Button>
                                {!tx.archived && (
                                  <Button size="icon" variant="ghost" className="h-7 w-7 text-text-secondary" onClick={() => handleArchive(tx.id)}>
                                    <Archive size={14} />
                                  </Button>
                                )}
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-divider">
                <span className="font-sans text-xs text-text-secondary">
                  Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, summary?.total_count || 0)} of {summary?.total_count || 0}
                </span>
                <Pagination>
                  <PaginationContent>
                    <PaginationItem>
                      <PaginationPrevious onClick={() => setPage(p => Math.max(0, p - 1))} className={page === 0 ? 'pointer-events-none opacity-50' : 'cursor-pointer'} />
                    </PaginationItem>
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      let p: number;
                      if (totalPages <= 5) p = i;
                      else if (page < 3) p = i;
                      else if (page > totalPages - 4) p = totalPages - 5 + i;
                      else p = page - 2 + i;
                      return (
                        <PaginationItem key={p}>
                          <PaginationLink
                            isActive={p === page}
                            onClick={() => setPage(p)}
                            className="cursor-pointer"
                          >
                            {p + 1}
                          </PaginationLink>
                        </PaginationItem>
                      );
                    })}
                    <PaginationItem>
                      <PaginationNext onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} className={page >= totalPages - 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'} />
                    </PaginationItem>
                  </PaginationContent>
                </Pagination>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Category Assignment Dialog */}
      <Dialog open={categoryDialogOpen} onOpenChange={setCategoryDialogOpen}>
        <DialogContent className="bg-surface border-divider text-text-primary">
          <DialogHeader>
            <DialogTitle className="font-sans text-sm">Assign Category</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p className="font-sans text-xs text-text-secondary mb-3">
              Transaction: {categoryDialogTx?.description}
            </p>
            <Select value={categoryDialogValue} onValueChange={setCategoryDialogValue}>
              <SelectTrigger className="bg-canvas border-divider"><SelectValue placeholder="Select a category" /></SelectTrigger>
              <SelectContent>
                {categories.map(cat => (
                  <SelectItem key={cat} value={cat}>{cat}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCategoryDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleCategoryAssign} disabled={!categoryDialogValue}>Assign</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
