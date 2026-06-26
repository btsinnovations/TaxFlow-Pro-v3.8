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
import { Loader2, ArrowRightLeft } from "lucide-react";

export interface FXRate {
  id: number;
  from_currency: string;
  to_currency: string;
  rate: number;
  effective_date: string;
}

export default function MultiCurrency() {
  const [tab, setTab] = useState<"rates" | "convert">("rates");
  const [rates, setRates] = useState<FXRate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sorting, setSorting] = useState<SortingState>([{ id: "effective_date", desc: true }]);
  const [search, setSearch] = useState("");

  const [amount, setAmount] = useState("1000");
  const [fromCurrency, setFromCurrency] = useState("USD");
  const [toCurrency, setToCurrency] = useState("EUR");
  const [asOf, setAsOf] = useState(new Date().toISOString().split("T")[0]);
  const [converted, setConverted] = useState<number | null>(null);
  const [convertLoading, setConvertLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (tab !== "rates") return;
    setLoading(true);
    setError(null);
    fetchWithAuth("/api/accounts/")
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text());
        return res.json();
      })
      .then((accounts) => {
        // Rates are not yet exposed as a list endpoint. We compute pairs from account currencies.
        const currencies: string[] = Array.from(new Set((accounts || []).map((a: any) => a.currency || "USD")));
        if (currencies.length === 0) currencies.push("USD");
        // Build all possible pairs except identical. For now we treat USD pairs as available.
        const pairs: FXRate[] = [];
        for (const from of currencies) {
          for (const to of currencies) {
            if (from !== to) {
              pairs.push({
                id: pairs.length + 1,
                from_currency: from,
                to_currency: to,
                rate: 1,
                effective_date: asOf,
              });
            }
          }
        }
        if (!cancelled) setRates(pairs);
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || "Failed to load rates");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [tab, asOf]);

  const filteredRows = useMemo(() => {
    if (!search.trim()) return rates;
    const q = search.toLowerCase();
    return rates.filter(
      (r) =>
        (r.from_currency || "").toLowerCase().includes(q) ||
        (r.to_currency || "").toLowerCase().includes(q)
    );
  }, [rates, search]);

  const columns = useMemo(
    () => [
      { accessorKey: "from_currency", header: "From" },
      { accessorKey: "to_currency", header: "To" },
      {
        accessorKey: "rate",
        header: "Rate",
        cell: ({ getValue }: any) => Number(getValue()).toFixed(6),
      },
      { accessorKey: "effective_date", header: "Effective Date" },
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

  async function handleConvert() {
    setConvertLoading(true);
    setConverted(null);
    try {
      const res = await fetchWithAuth("/api/fx/convert", {
        method: "POST",
        body: JSON.stringify({
          amount: Number(amount),
          from_currency: fromCurrency,
          to_currency: toCurrency,
          as_of: asOf,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setConverted(data.converted);
    } catch (e: any) {
      setError(e?.message || "Conversion failed");
    } finally {
      setConvertLoading(false);
    }
  }

  return (
    <ModuleShell
      title="Multi-Currency"
      description="Record transactions in foreign currencies and maintain home-currency equivalents using manual exchange rates."
      moduleId="3.11.08"
    >
      <Tabs value={tab} onValueChange={(v) => setTab(v as any)} className="w-full">
        <div className="flex flex-col md:flex-row gap-4 mb-4 items-start md:items-center justify-between">
          <div className="flex items-center gap-3">
            <TabsList className="bg-canvas border border-gold/30">
              <TabsTrigger value="rates" className="text-text-secondary data-[state=active]:text-gold data-[state=active]:bg-gold/10">
                Rates
              </TabsTrigger>
              <TabsTrigger value="convert" className="text-text-secondary data-[state=active]:text-gold data-[state=active]:bg-gold/10">
                Convert
              </TabsTrigger>
            </TabsList>
            {loading && <Loader2 className="w-5 h-5 animate-spin text-gold" />}
          </div>
          {tab === "rates" && (
            <Input
              placeholder="Search currencies..."
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

        <TabsContent value="rates" className="mt-0">
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
                      No currency pairs found.
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

        <TabsContent value="convert" className="mt-0">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end mb-6">
            <div className="space-y-1">
              <label className="text-xs text-text-secondary">Amount</label>
              <Input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="border-gold/30 bg-canvas text-text-primary"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-text-secondary">From</label>
              <Input
                value={fromCurrency}
                onChange={(e) => setFromCurrency(e.target.value.toUpperCase())}
                className="border-gold/30 bg-canvas text-text-primary"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-text-secondary">To</label>
              <Input
                value={toCurrency}
                onChange={(e) => setToCurrency(e.target.value.toUpperCase())}
                className="border-gold/30 bg-canvas text-text-primary"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-text-secondary">As of</label>
              <Input
                type="date"
                value={asOf}
                onChange={(e) => setAsOf(e.target.value)}
                className="border-gold/30 bg-canvas text-text-primary"
              />
            </div>
            <Button
              onClick={handleConvert}
              disabled={convertLoading}
              className="bg-gold text-black hover:bg-gold/90"
            >
              {convertLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRightLeft className="w-4 h-4" />}
              Convert
            </Button>
          </div>

          {converted !== null && (
            <div className="rounded-md border border-gold/30 bg-gold/5 p-6">
              <p className="text-sm text-text-secondary">Converted Amount</p>
              <p className="text-2xl text-text-primary">
                {converted.toLocaleString("en-US", { style: "currency", currency: toCurrency })}
              </p>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </ModuleShell>
  );
}
