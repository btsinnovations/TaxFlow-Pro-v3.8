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
import { fetchWithAuth, getAccounts } from "@/hooks/useAPI";
import { Loader2, PieChart, TrendingUp } from "lucide-react";

export interface BudgetLine {
  account_id: number;
  period: string;
  budget: number;
  actual: number;
  variance: number;
}

export default function BudgetForecast() {
  const [tab, setTab] = useState<"budget" | "forecast">("budget");
  const [period, setPeriod] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });
  const [startDate, setStartDate] = useState(new Date().toISOString().split("T")[0]);
  const [accounts, setAccounts] = useState<{ id: number; name: string }[]>([]);
  const [budgetRows, setBudgetRows] = useState<BudgetLine[]>([]);
  const [forecastRows, setForecastRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sorting, setSorting] = useState<SortingState>([{ id: "period", desc: true }]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    getAccounts()
      .then((data) => setAccounts((data || []).map((a: any) => ({ id: a.id, name: a.name }))))
      .catch((e) => setError(e?.message || "Failed to load accounts"));
  }, []);

  async function loadBudget() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth(`/api/budget/${period}/vs-actual`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setBudgetRows(data || []);
    } catch (e: any) {
      setError(e?.message || "Failed to load budget");
    } finally {
      setLoading(false);
    }
  }

  async function loadForecast() {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`/api/budget/cash-flow?start=${startDate}&months=6`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setForecastRows(data || []);
    } catch (e: any) {
      setError(e?.message || "Failed to load forecast");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (tab === "budget") loadBudget();
    else loadForecast();
  }, [tab]);

  const filteredRows = useMemo(() => {
    if (!search.trim()) return budgetRows;
    const q = search.toLowerCase();
    return budgetRows.filter((r) => {
      const acct = accounts.find((a) => a.id === r.account_id);
      return (acct?.name || "").toLowerCase().includes(q) || (r.period || "").includes(q);
    });
  }, [budgetRows, search, accounts]);

  const columns = useMemo(
    () => [
      {
        accessorKey: "account_id",
        header: "Account",
        cell: ({ getValue }: any) => {
          const id = Number(getValue());
          const acct = accounts.find((a) => a.id === id);
          return acct ? acct.name : `Account ${id}`;
        },
      },
      { accessorKey: "period", header: "Period" },
      {
        accessorKey: "budget",
        header: "Budget",
        cell: ({ getValue }: any) =>
          Number(getValue()).toLocaleString("en-US", { style: "currency", currency: "USD" }),
      },
      {
        accessorKey: "actual",
        header: "Actual",
        cell: ({ getValue }: any) =>
          Number(getValue()).toLocaleString("en-US", { style: "currency", currency: "USD" }),
      },
      {
        accessorKey: "variance",
        header: "Variance",
        cell: ({ getValue }: any) => {
          const v = Number(getValue());
          return (
            <span className={v >= 0 ? "text-green-400" : "text-red-400"}>
              {v.toLocaleString("en-US", { style: "currency", currency: "USD" })}
            </span>
          );
        },
      },
    ],
    [accounts]
  );

  const table = useReactTable({
    data: filteredRows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const totalVariance = useMemo(
    () => filteredRows.reduce((sum, r) => sum + (r.variance || 0), 0),
    [filteredRows]
  );

  return (
    <ModuleShell
      title="Budget & Cash Flow Forecasting"
      description="Set monthly/category budgets and forecast cash position based on recurring rules and open A/R, A/P."
      moduleId="3.11.12"
    >
      <Tabs value={tab} onValueChange={(v) => setTab(v as any)} className="w-full">
        <div className="flex flex-col md:flex-row gap-4 mb-4 items-start md:items-center justify-between">
          <div className="flex items-center gap-3 flex-wrap">
            <TabsList className="bg-canvas border border-gold/30">
              <TabsTrigger value="budget" className="text-text-secondary data-[state=active]:text-gold data-[state=active]:bg-gold/10">
                Budget vs Actual
              </TabsTrigger>
              <TabsTrigger value="forecast" className="text-text-secondary data-[state=active]:text-gold data-[state=active]:bg-gold/10">
                Cash Flow
              </TabsTrigger>
            </TabsList>
            {tab === "budget" && (
              <>
                <Input
                  value={period}
                  onChange={(e) => setPeriod(e.target.value)}
                  placeholder="YYYY-MM"
                  className="w-32 border-gold/30 bg-canvas text-text-primary"
                />
                <Button onClick={loadBudget} disabled={loading} className="bg-gold text-black hover:bg-gold/90">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <PieChart className="w-4 h-4" />}
                  Load
                </Button>
              </>
            )}
            {tab === "forecast" && (
              <>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-40 border-gold/30 bg-canvas text-text-primary"
                />
                <Button onClick={loadForecast} disabled={loading} className="bg-gold text-black hover:bg-gold/90">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <TrendingUp className="w-4 h-4" />}
                  Forecast
                </Button>
              </>
            )}
            {loading && <Loader2 className="w-5 h-5 animate-spin text-gold" />}
          </div>
          {tab === "budget" && (
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

        <TabsContent value="budget" className="mt-0">
          <div className="mb-4 flex items-center gap-2 text-text-secondary">
            <PieChart className="w-5 h-5 text-gold" />
            <span className="text-sm">
              {filteredRows.length} lines · Total variance{" "}
              <strong className={totalVariance >= 0 ? "text-green-400" : "text-red-400"}>
                {totalVariance.toLocaleString("en-US", { style: "currency", currency: "USD" })}
              </strong>
            </span>
          </div>
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
                      No budget lines for {period}.
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

        <TabsContent value="forecast" className="mt-0">
          <div className="rounded-md border border-divider overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="border-divider hover:bg-transparent">
                  <TableHead className="text-text-secondary">Date</TableHead>
                  <TableHead className="text-text-secondary">Projected Cash</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {forecastRows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={2} className="text-center text-text-secondary py-8">
                      Run forecast to see projection.
                    </TableCell>
                  </TableRow>
                ) : (
                  forecastRows.map((row, idx) => (
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
