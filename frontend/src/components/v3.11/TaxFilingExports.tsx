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
import { Loader2, FileText, Download } from "lucide-react";

export interface TaxMapping {
  id: number;
  coa_account_id: number;
  form: string;
  line: string;
  description?: string;
}

export interface ScheduleCLine {
  key: string;
  label: string;
  amount: number;
}

export default function TaxFilingExports() {
  const [startDate, setStartDate] = useState("2026-01-01");
  const [endDate, setEndDate] = useState("2026-12-31");
  const [scheduleC, setScheduleC] = useState<any | null>(null);
  const [mappings, setMappings] = useState<TaxMapping[]>([]);
  const [accounts, setAccounts] = useState<{ id: number; name: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sorting, setSorting] = useState<SortingState>([{ id: "form", desc: false }]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    getAccounts()
      .then((data) => setAccounts((data || []).map((a: any) => ({ id: a.id, name: a.name }))))
      .catch((e) => setError(e?.message || "Failed to load accounts"));
  }, []);

  async function loadScheduleC() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth("/api/tax-exports/schedule-c", {
        method: "POST",
        body: JSON.stringify({ start_date: startDate, end_date: endDate }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setScheduleC(data);
    } catch (e: any) {
      setError(e?.message || "Failed to load Schedule C");
    } finally {
      setLoading(false);
    }
  }

  async function loadMappings() {
    setLoading(true);
    try {
      const res = await fetchWithAuth("/api/tax-exports/mappings");
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setMappings(data || []);
    } catch (e: any) {
      setError(e?.message || "Failed to load mappings");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMappings();
  }, []);

  async function createMapping(accountId: number, line: string) {
    try {
      const res = await fetchWithAuth("/api/tax-exports/mappings", {
        method: "POST",
        body: JSON.stringify({ coa_account_id: accountId, form: "Schedule C", line, description: "" }),
      });
      if (!res.ok) throw new Error(await res.text());
      loadMappings();
    } catch (e: any) {
      setError(e?.message || "Failed to create mapping");
    }
  }

  const scheduleCLines: ScheduleCLine[] = useMemo(() => {
    if (!scheduleC) return [];
    return [
      { key: "line_1_gross_receipts", label: "Gross receipts", amount: scheduleC.line_1_gross_receipts || 0 },
      { key: "line_28_total_expenses", label: "Total expenses", amount: scheduleC.line_28_total_expenses || 0 },
      { key: "line_31_net_profit", label: "Net profit", amount: scheduleC.line_31_net_profit || 0 },
    ];
  }, [scheduleC]);

  const filteredMappings = useMemo(() => {
    if (!search.trim()) return mappings;
    const q = search.toLowerCase();
    return mappings.filter(
      (m) =>
        (m.form || "").toLowerCase().includes(q) ||
        (m.line || "").toLowerCase().includes(q) ||
        (m.description || "").toLowerCase().includes(q)
    );
  }, [mappings, search]);

  const columns = useMemo(
    () => [
      { accessorKey: "form", header: "Form" },
      { accessorKey: "line", header: "Line" },
      { accessorKey: "description", header: "Description" },
      {
        accessorKey: "coa_account_id",
        header: "COA Account",
        cell: ({ getValue }: any) => {
          const id = Number(getValue());
          const acct = accounts.find((a) => a.id === id);
          return acct ? acct.name : `Account ${id}`;
        },
      },
    ],
    [accounts]
  );

  const table = useReactTable({
    data: filteredMappings,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <ModuleShell
      title="Tax Filing Exports"
      description="Export categorized data to Schedule C, 1065, 1120S, and TurboTax/TaxAct compatible formats."
      moduleId="3.11.10"
    >
      <div className="flex flex-col md:flex-row gap-4 mb-4 items-start md:items-center justify-between">
        <div className="flex items-center gap-3 flex-wrap">
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
          <Button
            onClick={loadScheduleC}
            disabled={loading}
            className="bg-gold text-black hover:bg-gold/90"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
            Schedule C
          </Button>
          {loading && <Loader2 className="w-5 h-5 animate-spin text-gold" />}
        </div>
        <Input
          placeholder="Search mappings..."
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

      {scheduleC && (
        <div className="mb-6 rounded-md border border-gold/30 bg-gold/5 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-gold" />
              <h3 className="text-lg text-text-primary">{scheduleC.form} {scheduleC.year}</h3>
            </div>
            <Button
              variant="outline"
              className="border-gold/30 text-gold hover:bg-gold/10"
              onClick={() => {
                const blob = new Blob([JSON.stringify(scheduleC, null, 2)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `schedule-c-${scheduleC.year}.json`;
                a.click();
                URL.revokeObjectURL(url);
              }}
            >
              <Download className="w-4 h-4 mr-1" />
              Export JSON
            </Button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {scheduleCLines.map((line) => (
              <div key={line.key} className="rounded-md border border-divider bg-canvas p-4">
                <p className="text-xs text-text-secondary">{line.label}</p>
                <p className="text-lg text-text-primary">
                  {line.amount.toLocaleString("en-US", { style: "currency", currency: "USD" })}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-text-primary font-medium">Tax Line Mappings</h3>
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
                  No mappings found.
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
