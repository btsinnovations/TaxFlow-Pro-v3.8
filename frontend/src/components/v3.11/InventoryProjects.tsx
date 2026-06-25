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
import { Loader2, Package } from "lucide-react";

export interface InventoryItem {
  id: number;
  sku: string;
  name: string;
  qty_on_hand: number;
  unit_cost: number;
  valuation_method: string;
}

export default function InventoryProjects() {
  const [rows, setRows] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sorting, setSorting] = useState<SortingState>([{ id: "name", desc: false }]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchWithAuth("/api/inventory/")
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        if (!cancelled) setRows(data || []);
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || "Failed to load inventory");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const filteredRows = useMemo(() => {
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        (r.name || "").toLowerCase().includes(q) ||
        (r.sku || "").toLowerCase().includes(q) ||
        (r.valuation_method || "").toLowerCase().includes(q)
    );
  }, [rows, search]);

  const columns = useMemo(
    () => [
      { accessorKey: "sku", header: "SKU" },
      { accessorKey: "name", header: "Item Name" },
      {
        accessorKey: "qty_on_hand",
        header: "Qty on Hand",
        cell: ({ getValue }: any) => Number(getValue()).toLocaleString(),
      },
      {
        accessorKey: "unit_cost",
        header: "Unit Cost",
        cell: ({ getValue }: any) =>
          Number(getValue()).toLocaleString("en-US", { style: "currency", currency: "USD" }),
      },
      { accessorKey: "valuation_method", header: "Valuation" },
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

  const totalValue = useMemo(
    () => filteredRows.reduce((sum, r) => sum + (r.qty_on_hand || 0) * (r.unit_cost || 0), 0),
    [filteredRows]
  );

  return (
    <ModuleShell
      title="Inventory & Project Tags"
      description="Lightweight inventory tracking with average/FIFO valuation and project-based cost tagging for job-costing."
      moduleId="3.11.07"
    >
      <div className="flex flex-col md:flex-row gap-4 mb-4 items-start md:items-center justify-between">
        <div className="flex items-center gap-2 text-text-secondary">
          <Package className="w-5 h-5 text-gold" />
          <span className="text-sm">{filteredRows.length} items · Total value {totalValue.toLocaleString("en-US", { style: "currency", currency: "USD" })}</span>
          {loading && <Loader2 className="w-5 h-5 animate-spin text-gold" />}
        </div>
        <Input
          placeholder="Search inventory..."
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
                  No inventory items found.
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
