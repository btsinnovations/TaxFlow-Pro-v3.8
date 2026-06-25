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
import { Loader2, Wallet } from "lucide-react";

export interface Lot {
  id: number;
  symbol: string;
  shares: number;
  cost_basis: number;
  acquisition_date: string;
}

export interface Holding {
  account_id: number;
  symbol: string;
  total_shares: number;
  total_cost: number;
  lots: Lot[];
}

export interface LoanSchedule {
  id: number;
  account_id: number;
  payment_amount: number;
  schedule: Array<{
    payment_number: number;
    payment_date: string;
    principal: number;
    interest: number;
    balance: number;
  }>;
}

export default function LiabilitiesInvestments() {
  const [tab, setTab] = useState<"loans" | "credit" | "holdings">("loans");
  const [accounts, setAccounts] = useState<{ id: number; name: string; institution?: string }[]>([]);
  const [accountId, setAccountId] = useState<string>("");
  const [rows, setRows] = useState<any[]>([]);
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sorting, setSorting] = useState<SortingState>([{ id: "date", desc: false }]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    getAccounts()
      .then((data) => {
        const list = (data || []).map((a: any) => ({ id: a.id, name: a.name, institution: a.institution }));
        setAccounts(list);
        if (list.length > 0 && !accountId) {
          setAccountId(String(list[0].id));
        }
      })
      .catch((e) => setError(e?.message || "Failed to load accounts"));
  }, [accountId]);

  useEffect(() => {
    if (!accountId) {
      setRows([]);
      setDetail(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);

    const load = async () => {
      try {
        if (tab === "holdings") {
          const res = await fetchWithAuth(`/api/investments/${accountId}/holdings`);
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          if (!cancelled) {
            const lots = (data || []).flatMap((h: any) => (h.lots || []).map((l: any) => ({ ...l, symbol: h.symbol, total_shares: h.total_shares })));
            setRows(lots);
            setDetail(null);
          }
        } else if (tab === "credit") {
          const res = await fetchWithAuth(`/api/liabilities/${accountId}/available-credit`);
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          if (!cancelled) {
            setDetail(data);
            setRows([]);
          }
        } else {
          setRows([]);
          setDetail(null);
        }
      } catch (e: any) {
        if (!cancelled) setError(e?.message || `Failed to load ${tab}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
  }, [accountId, tab]);

  const filteredRows = useMemo(() => {
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        (r.symbol || "").toLowerCase().includes(q) ||
        (r.acquisition_date || "").toLowerCase().includes(q)
    );
  }, [rows, search]);

  const columns = useMemo(
    () => [
      { accessorKey: "symbol", header: "Symbol" },
      {
        accessorKey: "shares",
        header: "Shares",
        cell: ({ getValue }: any) => Number(getValue()).toLocaleString(),
      },
      {
        accessorKey: "cost_basis",
        header: "Cost Basis",
        cell: ({ getValue }: any) =>
          Number(getValue()).toLocaleString("en-US", { style: "currency", currency: "USD" }),
      },
      { accessorKey: "acquisition_date", header: "Acquisition Date" },
      {
        accessorKey: "total_shares",
        header: "Total Held",
        cell: ({ getValue }: any) => Number(getValue()).toLocaleString(),
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

  const totalCost = useMemo(
    () => filteredRows.reduce((sum, r) => sum + (r.shares || 0) * (r.cost_basis || 0), 0),
    [filteredRows]
  );

  return (
    <ModuleShell
      title="Loans, Credit Lines & Investments"
      description="Track liability and asset accounts: loan amortization, credit-line available balance, and investment lot holdings."
      moduleId="3.11.06"
    >
      <Tabs value={tab} onValueChange={(v) => setTab(v as any)} className="w-full">
        <div className="flex flex-col md:flex-row gap-4 mb-4 items-start md:items-center justify-between">
          <div className="flex items-center gap-3 flex-wrap">
            <TabsList className="bg-canvas border border-gold/30">
              <TabsTrigger value="loans" className="text-text-secondary data-[state=active]:text-gold data-[state=active]:bg-gold/10">
                Loans
              </TabsTrigger>
              <TabsTrigger value="credit" className="text-text-secondary data-[state=active]:text-gold data-[state=active]:bg-gold/10">
                Credit Lines
              </TabsTrigger>
              <TabsTrigger value="holdings" className="text-text-secondary data-[state=active]:text-gold data-[state=active]:bg-gold/10">
                Holdings
              </TabsTrigger>
            </TabsList>
            <select
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="h-9 rounded-md border border-gold/30 bg-canvas px-3 text-sm text-text-primary"
            >
              {accounts.map((a) => (
                <option key={a.id} value={String(a.id)}>
                  {a.name}
                </option>
              ))}
            </select>
            {loading && <Loader2 className="w-5 h-5 animate-spin text-gold" />}
          </div>
          <Input
            placeholder="Search holdings..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full md:w-64 border-gold/30 bg-canvas text-text-primary"
          />
        </div>

        {error && (
          <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300 mb-4">
            {error}
          </div>
        )}

        <TabsContent value="loans" className="mt-0">
          <div className="rounded-md border border-divider p-8 text-center text-text-secondary">
            Loan schedule creation will be added in a future release.
          </div>
        </TabsContent>

        <TabsContent value="credit" className="mt-0">
          {detail ? (
            <div className="flex items-center gap-4 rounded-md border border-gold/30 bg-gold/5 p-6">
              <Wallet className="w-8 h-8 text-gold" />
              <div>
                <p className="text-sm text-text-secondary">Available Credit</p>
                <p className="text-2xl text-text-primary">
                  {Number(detail.available_credit || 0).toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                  })}
                </p>
              </div>
            </div>
          ) : (
            <div className="rounded-md border border-divider p-8 text-center text-text-secondary">
              Select a credit-line account to view available credit.
            </div>
          )}
        </TabsContent>

        <TabsContent value="holdings" className="mt-0">
          <div className="mb-4 flex items-center gap-2 text-text-secondary">
            <Wallet className="w-5 h-5 text-gold" />
            <span className="text-sm">
              {filteredRows.length} lots · Total cost {totalCost.toLocaleString("en-US", { style: "currency", currency: "USD" })}
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
                      No holdings found.
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
      </Tabs>
    </ModuleShell>
  );
}
