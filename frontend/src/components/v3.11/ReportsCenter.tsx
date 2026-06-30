import { useEffect, useMemo, useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type SortingState,
} from "@tanstack/react-table";
import ModuleShell from "@/components/v3.11/ModuleShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fetchWithAuth } from "@/hooks/useAPI";
import { Loader2, FileText, Download } from "lucide-react";

export interface TrialBalanceRow {
  account_id: number;
  code: string;
  name: string;
  debit: number;
  credit: number;
}

export default function ReportsCenter() {
  const [tab, setTab] = useState<"pnl" | "trial" | "cashflow">("pnl");
  const [startDate, setStartDate] = useState("2026-01-01");
  const [endDate, setEndDate] = useState("2026-12-31");
  const [asOf, setAsOf] = useState("2026-12-31");
  const [pnl, setPnl] = useState<any | null>(null);
  const [trial, setTrial] = useState<TrialBalanceRow[]>([]);
  const [cashFlow, setCashFlow] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sorting, setSorting] = useState<SortingState>([{ id: "code", desc: false }]);
  const [search, setSearch] = useState("");

  async function loadPnl() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth("/api/reports/profit-and-loss", {
        method: "POST",
        body: JSON.stringify({ start_date: startDate, end_date: endDate }),
      });
      if (!res.ok) throw new Error(await res.text());
      setPnl(await res.json());
    } catch (e: any) {
      setError(e?.message || "Failed to load P&L");
    } finally {
      setLoading(false);
    }
  }

  async function loadTrial() {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`/api/reports/trial-balance?as_of=${asOf}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setTrial(data.rows || []);
    } catch (e: any) {
      setError(e?.message || "Failed to load trial balance");
    } finally {
      setLoading(false);
    }
  }

  async function loadCashFlow() {
    setLoading(true);
    try {
      const res = await fetchWithAuth("/api/reports/cash-flow", {
        method: "POST",
        body: JSON.stringify({ start_date: startDate, end_date: endDate }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setCashFlow(data || []);
    } catch (e: any) {
      setError(e?.message || "Failed to load cash flow");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPnl();
  }, []);

  const filteredRows = useMemo(() => {
    if (!search.trim()) return trial;
    const q = search.toLowerCase();
    return trial.filter(
      (r) =>
        (r.name || "").toLowerCase().includes(q) ||
        (r.code || "").toLowerCase().includes(q)
    );
  }, [trial, search]);

  const columns = useMemo(
    () => [
      { accessorKey: "code", header: "Code" },
      { accessorKey: "name", header: "Account" },
      {
        accessorKey: "debit",
        header: "Debit",
        cell: ({ getValue }: any) =>
          Number(getValue()).toLocaleString("en-US", { style: "currency", currency: "USD" }),
      },
      {
        accessorKey: "credit",
        header: "Credit",
        cell: ({ getValue }: any) =>
          Number(getValue()).toLocaleString("en-US", { style: "currency", currency: "USD" }),
      },
    ],
    []
  );

  const table = useReactTable({
    data: filteredRows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <ModuleShell
      title="Reports Center"
      description="Standard financial reports: P&L, Balance Sheet, Cash Flow, Trial Balance, and General Ledger detail."
      moduleId="3.11.11"
    >
      <Tabs value={tab} onValueChange={(v) => setTab(v as any)} className="w-full">
        <div className="flex flex-col md:flex-row gap-4 mb-4 items-start md:items-center justify-between">
          <div className="flex items-center gap-3 flex-wrap">
            <TabsList className="bg-canvas border border-gold/30">
              <TabsTrigger value="pnl" className="text-text-secondary data-[state=active]:text-gold data-[state=active]:bg-gold/10">
                P&L
              </TabsTrigger>
              <TabsTrigger value="trial" className="text-text-secondary data-[state=active]:text-gold data-[state=active]:bg-gold/10">
                Trial Balance
              </TabsTrigger>
              <TabsTrigger value="cashflow" className="text-text-secondary data-[state=active]:text-gold data-[state=active]:bg-gold/10">
                Cash Flow
              </TabsTrigger>
            </TabsList>
            {tab === "pnl" && (
              <>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-40 border-gold/30 bg-canvas text-text-primary"
                />
                <Input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-40 border-gold/30 bg-canvas text-text-primary"
                />
                <Button onClick={loadPnl} disabled={loading} className="bg-gold text-black hover:bg-gold/90">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
                  Run
                </Button>
              </>
            )}
            {tab === "trial" && (
              <>
                <Input
                  type="date"
                  value={asOf}
                  onChange={(e) => setAsOf(e.target.value)}
                  className="w-40 border-gold/30 bg-canvas text-text-primary"
                />
                <Button onClick={loadTrial} disabled={loading} className="bg-gold text-black hover:bg-gold/90">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
                  Run
                </Button>
              </>
            )}
            {tab === "cashflow" && (
              <>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-40 border-gold/30 bg-canvas text-text-primary"
                />
                <Button onClick={loadCashFlow} disabled={loading} className="bg-gold text-black hover:bg-gold/90">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
                  Run
                </Button>
              </>
            )}
            {loading && <Loader2 className="w-5 h-5 animate-spin text-gold" />}
          </div>
          {tab === "trial" && (
            <Input
              placeholder="Search accounts..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full md:w-64 border-gold/30 bg-canvas text-text-primary"
            />
          )}
        </div>

        {error && (
          <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300 mb-4">
            {error}
          </div>
        )}

        <TabsContent value="pnl" className="mt-0">
          {pnl && (
            <div className="rounded-md border border-gold/30 bg-gold/5 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg text-text-primary">Profit & Loss</h3>
                <Button
                  variant="outline"
                  className="border-gold/30 text-gold hover:bg-gold/10"
                  onClick={() => downloadJson(pnl, `pnl-${startDate}-${endDate}.json`)}
                >
                  <Download className="w-4 h-4 mr-1" />
                  Export
                </Button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="rounded-md border border-divider bg-canvas p-4">
                  <p className="text-xs text-text-secondary">Income</p>
                  <p className="text-lg text-green-400">{pnl.income.toLocaleString("en-US", { style: "currency", currency: "USD" })}</p>
                </div>
                <div className="rounded-md border border-divider bg-canvas p-4">
                  <p className="text-xs text-text-secondary">Expenses</p>
                  <p className="text-lg text-red-400">{pnl.expenses.toLocaleString("en-US", { style: "currency", currency: "USD" })}</p>
                </div>
                <div className="rounded-md border border-divider bg-canvas p-4">
                  <p className="text-xs text-text-secondary">Net</p>
                  <p className="text-lg text-text-primary">{pnl.net.toLocaleString("en-US", { style: "currency", currency: "USD" })}</p>
                </div>
              </div>
            </div>
          )}
        </TabsContent>

        <TabsContent value="trial" className="mt-0">
          <div className="rounded-md border border-divider overflow-hidden">
            <Table>
              <TableHeader>
                {table.getHeaderGroups().map((hg) => (
                  <TableRow key={hg.id} className="border-divider hover:bg-transparent">
                    {hg.headers.map((h) => (
                      <TableHead key={h.id} className="text-text-secondary">
                        {h.isPlaceholder ? null : (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={h.column.getToggleSortingHandler()}
                            className="px-0 text-text-secondary hover:text-gold hover:bg-transparent"
                          >
                            {flexRender(h.column.columnDef.header, h.getContext())}
                            <span className="ml-1 text-xs">
                              {h.column.getIsSorted() === "asc" ? "↑" : h.column.getIsSorted() === "desc" ? "↓" : "↕"}
                            </span>
                          </Button>
                        )}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {table.getRowModel().rows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={columns.length} className="text-center text-text-secondary py-8">
                      No trial balance rows.
                    </TableCell>
                  </TableRow>
                ) : (
                  table.getRowModel().rows.map((row) => (
                    <TableRow key={row.id} className="border-divider">
                      {row.getVisibleCells().map((cell) => (
                        <TableCell key={cell.id} className="text-text-primary">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="cashflow" className="mt-0">
          <div className="rounded-md border border-divider overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="border-divider hover:bg-transparent">
                  <TableHead className="text-text-secondary">Month</TableHead>
                  <TableHead className="text-text-secondary">Projected Cash</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {cashFlow.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={2} className="text-center text-text-secondary py-8">
                      Run cash flow forecast to see projection.
                    </TableCell>
                  </TableRow>
                ) : (
                  cashFlow.map((row, idx) => (
                    <TableRow key={idx} className="border-divider">
                      <TableCell className="text-text-primary">{row.date}</TableCell>
                      <TableCell className="text-text-primary">
                        {Number(row.projected_cash || 0).toLocaleString("en-US", { style: "currency", currency: "USD" })}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
      </Tabs>
    </ModuleShell>
  );
}

function downloadJson(data: any, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
