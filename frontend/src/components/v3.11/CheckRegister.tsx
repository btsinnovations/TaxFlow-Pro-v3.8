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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fetchWithAuth, getAccounts } from "@/hooks/useAPI";
import { Loader2 } from "lucide-react";

export interface CheckRow {
  id: number;
  date: string;
  description: string;
  amount: number;
  tx_type: string;
  workpaper_ref?: string | null;
}

export default function CheckRegister() {
  const [accounts, setAccounts] = useState<{ id: number; name: string; institution?: string }[]>([]);
  const [accountId, setAccountId] = useState<string>("");
  const [rows, setRows] = useState<CheckRow[]>([]);
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
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchWithAuth(`/api/checks/${accountId}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        if (!cancelled) setRows(data || []);
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || "Failed to load checks");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [accountId]);

  const filteredRows = useMemo(() => {
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        (r.description || "").toLowerCase().includes(q) ||
        (r.workpaper_ref || "").toLowerCase().includes(q) ||
        (r.tx_type || "").toLowerCase().includes(q)
    );
  }, [rows, search]);

  const columns = useMemo(
    () => [
      { accessorKey: "date", header: "Date" },
      { accessorKey: "description", header: "Payee / Description" },
      {
        accessorKey: "amount",
        header: "Amount",
        cell: ({ getValue }: any) => {
          const v = Number(getValue());
          return (
            <span className={v < 0 ? "text-red-400" : "text-green-400"}>
              {v.toLocaleString("en-US", { style: "currency", currency: "USD" })}
            </span>
          );
        },
      },
      { accessorKey: "tx_type", header: "Type" },
      { accessorKey: "workpaper_ref", header: "Workpaper Ref" },
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
      title="Check Register"
      description="Specialized register for checking accounts with check number tracking, payee/memo, status, and running balance."
      moduleId="3.11.05"
    >
      <div className="flex flex-col md:flex-row gap-4 mb-4 items-start md:items-center justify-between">
        <div className="flex items-center gap-3">
          <Select value={accountId} onValueChange={setAccountId}>
            <SelectTrigger className="w-[260px] border-gold/30 bg-canvas text-text-primary">
              <SelectValue placeholder="Select account" />
            </SelectTrigger>
            <SelectContent className="bg-canvas border-gold/30">
              {accounts.map((a) => (
                <SelectItem key={a.id} value={String(a.id)} className="text-text-primary">
                  {a.name} {a.institution ? `(${a.institution})` : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {loading && <Loader2 className="w-5 h-5 animate-spin text-gold" />}
        </div>
        <Input
          placeholder="Search checks..."
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
                  {accountId ? "No checks found." : "Select an account to view checks."}
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
