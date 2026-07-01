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
import { fetchWithAuth } from "@/hooks/useAPI";
import { log } from "@/lib/logger";
import { Edit3, Trash2, Split, Loader2 } from "lucide-react";

export interface RegisterRow {
  id: number;
  date: string;
  description: string;
  amount: number;
  category: string;
  account_name?: string;
  running_balance?: number;
  gl_account_id?: number | null;
}

interface RegisterProps {
  accountId?: string | number;
}

export default function Register({ accountId }: RegisterProps) {
  const [rows, setRows] = useState<RegisterRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sorting, setSorting] = useState<SortingState>([{ id: "date", desc: false }]);
  const [search, setSearch] = useState("");

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      let url = "/api/transactions/?limit=500";
      if (accountId != null) url += `&account_id=${accountId}`;
      const res = await fetchWithAuth(url);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setRows(data);
    } catch (e: any) {
      setError(e?.message || "Failed to load register");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId]);

  const filteredRows = useMemo(() => {
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        (r.description || "").toLowerCase().includes(q) ||
        (r.category || "").toLowerCase().includes(q) ||
        (r.account_name || "").toLowerCase().includes(q)
    );
  }, [rows, search]);

  const columns = useMemo(
    () => [
      {
        accessorKey: "date",
        header: "Date",
        cell: (info: any) => info.getValue() || "—",
      },
      {
        accessorKey: "description",
        header: "Description",
      },
      {
        accessorKey: "amount",
        header: "Amount",
        cell: (info: any) => {
          const value = info.getValue();
          return value != null ? `$${Number(value).toFixed(2)}` : "—";
        },
      },
      {
        accessorKey: "category",
        header: "Category",
      },
      {
        accessorKey: "account_name",
        header: "Account",
        cell: (info: any) => info.getValue() || "—",
      },
      {
        accessorKey: "running_balance",
        header: "Running Balance",
        cell: (info: any) => {
          const value = info.getValue();
          return value != null ? `$${Number(value).toFixed(2)}` : "—";
        },
      },
      {
        id: "actions",
        header: "Actions",
        cell: (info: any) => {
          const row = info.row.original as RegisterRow;
          return (
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                title="Split"
                onClick={() => handleSplit(row.id)}
              >
                <Split className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                title="Edit"
                onClick={() => handleEdit(row.id)}
              >
                <Edit3 className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                title="Delete"
                onClick={() => handleDelete(row.id)}
              >
                <Trash2 className="w-4 h-4 text-red-500" />
              </Button>
            </div>
          );
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

  const handleSplit = (id: number) => {
    log.log("split stub", id);
  };

  const handleEdit = (id: number) => {
    log.log("edit stub", id);
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm("Delete this transaction?")) return;
    try {
      const res = await fetchWithAuth(`/api/transactions/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(await res.text());
      setRows((prev) => prev.filter((r) => r.id !== id));
    } catch (e: any) {
      setError(e?.message || "Failed to delete transaction");
    }
  };

  return (
    <ModuleShell
      title="Unified Register"
      description="All transactions across accounts. Sort, filter, split, edit, or delete entries."
      moduleId="3.11.03"
    >
      <div className="flex items-center justify-between gap-4 mb-4">
        <Input
          placeholder="Search description, category, account..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm bg-canvas border-divider text-text-primary"
        />
        <Button
          variant="outline"
          onClick={load}
          disabled={loading}
          className="border-gold/30 text-gold hover:bg-gold/10"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Refresh"}
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-red-400 mb-4">
          {error}
        </div>
      )}

      <div className="rounded-lg border border-divider overflow-hidden">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id} className="border-divider hover:bg-transparent">
                {hg.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className="text-text-secondary cursor-pointer select-none"
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="text-center text-text-secondary py-8">
                  No transactions found.
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} className="border-divider hover:bg-gold/5">
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
