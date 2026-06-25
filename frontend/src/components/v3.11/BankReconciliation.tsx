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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fetchWithAuth, getAccounts } from "@/hooks/useAPI";
import { Loader2, RefreshCw, CheckCircle2 } from "lucide-react";

export interface MatchRow {
  statement_date: string;
  statement_description: string;
  statement_amount: number;
  ledger_id: number | null;
  ledger_date: string | null;
  ledger_amount: number | null;
  confidence: number;
}

export default function BankReconciliation() {
  const [accounts, setAccounts] = useState<{ id: number; name: string; institution?: string }[]>([]);
  const [accountId, setAccountId] = useState<string>("");
  const [rows, setRows] = useState<MatchRow[]>([]);
  const [status, setStatus] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sorting, setSorting] = useState<SortingState>([{ id: "statement_date", desc: false }]);
  const [search, setSearch] = useState("");
  const [statementBalance, setStatementBalance] = useState("");
  const [statementDate, setStatementDate] = useState(new Date().toISOString().split("T")[0]);
  const [importId, setImportId] = useState<number | null>(null);

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

  async function importStatement() {
    if (!accountId || !statementBalance || !statementDate) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth("/api/reconciliation/import", {
        method: "POST",
        body: JSON.stringify({
          account_id: Number(accountId),
          statement_balance: Number(statementBalance),
          statement_date: statementDate,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setImportId(data.id);
      loadStatus(data.id);
    } catch (e: any) {
      setError(e?.message || "Failed to import statement");
      setLoading(false);
    }
  }

  async function loadStatus(id: number) {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`/api/reconciliation/${id}/status`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setStatus(data);
      setRows((data.matches || []).map((m: any) => ({ ...m, confidence: m.confidence || 1 })));
    } catch (e: any) {
      setError(e?.message || "Failed to load status");
    } finally {
      setLoading(false);
    }
  }

  async function runAutoMatch() {
    if (!importId) return;
    setLoading(true);
    try {
      const res = await fetchWithAuth(`/api/reconciliation/${importId}/auto-match`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setRows((data || []).map((m: any) => ({ ...m, confidence: m.confidence || 1 })));
    } catch (e: any) {
      setError(e?.message || "Auto-match failed");
    } finally {
      setLoading(false);
    }
  }

  const filteredRows = useMemo(() => {
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        (r.statement_description || "").toLowerCase().includes(q) ||
        String(r.statement_amount || "").includes(q)
    );
  }, [rows, search]);

  const columns = useMemo(
    () => [
      { accessorKey: "statement_date", header: "Statement Date" },
      { accessorKey: "statement_description", header: "Description" },
      {
        accessorKey: "statement_amount",
        header: "Amount",
        cell: ({ getValue }: any) =>
          Number(getValue()).toLocaleString("en-US", { style: "currency", currency: "USD" }),
      },
      { accessorKey: "ledger_date", header: "Ledger Date" },
      {
        accessorKey: "ledger_amount",
        header: "Ledger Amount",
        cell: ({ getValue }: any) =>
          getValue() != null
            ? Number(getValue()).toLocaleString("en-US", { style: "currency", currency: "USD" })
            : "—",
      },
      {
        accessorKey: "confidence",
        header: "Match",
        cell: ({ getValue }: any) => {
          const v = Number(getValue());
          return v >= 1 ? <CheckCircle2 className="w-4 h-4 text-green-400" /> : <span className="text-text-secondary">—</span>;
        },
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

  const matchedCount = useMemo(() => rows.filter((r) => r.confidence >= 1).length, [rows]);

  return (
    <ModuleShell
      title="Bank Reconciliation"
      description="Match imported bank statement transactions against ledger transactions and mark cleared items."
      moduleId="3.11.09"
    >
      <div className="flex flex-col md:flex-row gap-4 mb-4 items-start md:items-center justify-between">
        <div className="flex items-center gap-3 flex-wrap">
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
          <Input
            type="number"
            placeholder="Statement balance"
            value={statementBalance}
            onChange={(e) => setStatementBalance(e.target.value)}
            className="w-40 border-gold/30 bg-canvas text-text-primary"
          />
          <Input
            type="date"
            value={statementDate}
            onChange={(e) => setStatementDate(e.target.value)}
            className="w-40 border-gold/30 bg-canvas text-text-primary"
          />
          <Button
            onClick={importStatement}
            disabled={loading || !accountId || !statementBalance}
            className="bg-gold text-black hover:bg-gold/90"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Import
          </Button>
          {importId && (
            <Button
              onClick={runAutoMatch}
              disabled={loading}
              variant="outline"
              className="border-gold/30 text-gold hover:bg-gold/10"
            >
              Auto-match
            </Button>
          )}
          {loading && <Loader2 className="w-5 h-5 animate-spin text-gold" />}
        </div>
        <Input
          placeholder="Search matches..."
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

      {status && (
        <div className="mb-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="rounded-md border border-gold/30 bg-gold/5 p-4">
            <p className="text-xs text-text-secondary">Statement Balance</p>
            <p className="text-lg text-text-primary">
              {Number(status.statement_balance || 0).toLocaleString("en-US", { style: "currency", currency: "USD" })}
            </p>
          </div>
          <div className="rounded-md border border-gold/30 bg-gold/5 p-4">
            <p className="text-xs text-text-secondary">Ledger Balance</p>
            <p className="text-lg text-text-primary">
              {Number(status.ledger_balance || 0).toLocaleString("en-US", { style: "currency", currency: "USD" })}
            </p>
          </div>
          <div className="rounded-md border border-gold/30 bg-gold/5 p-4">
            <p className="text-xs text-text-secondary">Matched</p>
            <p className="text-lg text-text-primary">{matchedCount} / {rows.length}</p>
          </div>
        </div>
      )}

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
                  Import a statement and run auto-match to see matches.
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
    </ModuleShell>
  );
}
