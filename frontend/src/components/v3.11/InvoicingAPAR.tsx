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
import { Loader2, FileText, AlertCircle } from "lucide-react";

export interface InvoiceRow {
  id: number;
  contact_name: string;
  invoice_number: string;
  issue_date: string;
  due_date: string;
  total: number;
  amount_paid: number;
  balance: number;
  status: string;
  aging_bucket: string;
  is_bill?: boolean;
}

export default function InvoicingAPAR() {
  const [tab, setTab] = useState<"invoices" | "bills">("invoices");
  const [rows, setRows] = useState<InvoiceRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sorting, setSorting] = useState<SortingState>([{ id: "due_date", desc: false }]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchWithAuth(`/api/invoicing/${tab}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        if (!cancelled) setRows((data || []).map((r: any) => ({ ...r, is_bill: tab === "bills" })));
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || `Failed to load ${tab}`);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [tab]);

  const filteredRows = useMemo(() => {
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (r) =>
        (r.contact_name || "").toLowerCase().includes(q) ||
        (r.invoice_number || "").toLowerCase().includes(q) ||
        (r.status || "").toLowerCase().includes(q)
    );
  }, [rows, search]);

  const columns = useMemo(
    () => [
      { accessorKey: "invoice_number", header: "Number" },
      { accessorKey: "contact_name", header: "Contact" },
      { accessorKey: "issue_date", header: "Issued" },
      { accessorKey: "due_date", header: "Due" },
      {
        accessorKey: "total",
        header: "Total",
        cell: ({ getValue }: any) =>
          Number(getValue()).toLocaleString("en-US", { style: "currency", currency: "USD" }),
      },
      {
        accessorKey: "balance",
        header: "Balance",
        cell: ({ getValue }: any) => {
          const v = Number(getValue());
          return (
            <span className={v > 0 ? "text-gold" : "text-text-secondary"}>
              {v.toLocaleString("en-US", { style: "currency", currency: "USD" })}
            </span>
          );
        },
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ getValue }: any) => {
          const v = String(getValue());
          const color =
            v === "paid"
              ? "text-green-400"
              : v === "overdue"
              ? "text-red-400"
              : "text-gold";
          return <span className={`capitalize ${color}`}>{v}</span>;
        },
      },
      {
        accessorKey: "aging_bucket",
        header: "Aging",
        cell: ({ row }: any) => {
          const status = row.original.status;
          const bucket = row.original.aging_bucket;
          return status !== "paid" ? (
            <div className="flex items-center gap-1">
              <AlertCircle className="w-3 h-3 text-gold" />
              <span className="text-text-secondary text-xs">{bucket}</span>
            </div>
          ) : null;
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

  const outstanding = useMemo(
    () => filteredRows.filter((r) => r.status !== "paid").reduce((sum, r) => sum + (r.balance || 0), 0),
    [filteredRows]
  );

  return (
    <ModuleShell
      title="Invoicing / A/P / A/R"
      description="Lightweight invoice creation for A/R and bill recording for A/P with payment application and aging."
      moduleId="3.11.13"
    >
      <Tabs value={tab} onValueChange={(v) => setTab(v as any)} className="w-full">
        <div className="flex flex-col md:flex-row gap-4 mb-4 items-start md:items-center justify-between">
          <div className="flex items-center gap-3">
            <TabsList className="bg-canvas border border-gold/30">
              <TabsTrigger value="invoices" className="text-text-secondary data-[state=active]:text-gold data-[state=active]:bg-gold/10">
                Invoices
              </TabsTrigger>
              <TabsTrigger value="bills" className="text-text-secondary data-[state=active]:text-gold data-[state=active]:bg-gold/10">
                Bills
              </TabsTrigger>
            </TabsList>
            {loading && <Loader2 className="w-5 h-5 animate-spin text-gold" />}
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-text-secondary">
              Outstanding: <strong className="text-gold">{outstanding.toLocaleString("en-US", { style: "currency", currency: "USD" })}</strong>
            </span>
            <Input
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full md:w-64 border-gold/30 bg-canvas text-text-primary"
            />
          </div>
        </div>

        {error && (
          <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300 mb-4">
            {error}
          </div>
        )}

        <TabsContent value="invoices" className="mt-0">
          {renderTable(table, columns.length)}
        </TabsContent>
        <TabsContent value="bills" className="mt-0">
          {renderTable(table, columns.length)}
        </TabsContent>
      </Tabs>
    </ModuleShell>
  );
}

function renderTable(table: any, colSpan: number) {
  return (
    <div className="rounded-md border border-divider overflow-hidden">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((hg: any) => (
            <TableRow key={hg.id} className="border-divider hover:bg-transparent">
              {hg.headers.map((h: any) => (
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
              <TableCell colSpan={colSpan} className="text-center text-text-secondary py-8">
                No records found.
              </TableCell>
            </TableRow>
          ) : (
            table.getRowModel().rows.map((row: any) => (
              <TableRow key={row.id} className="border-divider">
                {row.getVisibleCells().map((cell: any) => (
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
  );
}
