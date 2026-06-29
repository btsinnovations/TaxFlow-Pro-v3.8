import { useState } from "react";
import ModuleShell from "./ModuleShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { exportTransactions, exportGeneralLedger, exportTrialBalance, exportProfitLoss, exportBalanceSheet } from "@/hooks/useAPIExtensions";
import { Download, Loader2, AlertTriangle, CheckCircle2 } from "lucide-react";

const EXPORT_TYPES = [
  { key: "transactions", label: "Transactions", fn: exportTransactions },
  { key: "general-ledger", label: "General Ledger", fn: exportGeneralLedger },
  { key: "trial-balance", label: "Trial Balance", fn: exportTrialBalance },
  { key: "profit-loss", label: "Profit & Loss", fn: exportProfitLoss },
  { key: "balance-sheet", label: "Balance Sheet", fn: exportBalanceSheet },
] as const;

export default function ExportManager() {
  const [exportType, setExportType] = useState<string>("transactions");
  const [startDate, setStartDate] = useState("2026-01-01");
  const [endDate, setEndDate] = useState("2026-12-31");
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleExport() {
    const config = EXPORT_TYPES.find((t) => t.key === exportType);
    if (!config) return;
    setExporting(true);
    setError(null);
    setMessage(null);
    try {
      const blob = await config.fn({ start_date: startDate, end_date: endDate });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${exportType}-${startDate}-to-${endDate}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      setMessage(`${config.label} exported successfully.`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setExporting(false);
    }
  }

  return (
    <ModuleShell title="Export Manager" description="Export financial data: transactions, GL, trial balance, P&L, and balance sheet." moduleId="M07">
      <div className="max-w-lg space-y-4">
        <div>
          <Label className="text-text-secondary">Export Type</Label>
          <select value={exportType} onChange={(e) => setExportType(e.target.value)} className="w-full rounded-md border border-gold/30 bg-canvas text-text-primary p-2">
            {EXPORT_TYPES.map((t) => (
              <option key={t.key} value={t.key}>{t.label}</option>
            ))}
          </select>
        </div>

        <div className="flex gap-4">
          <div className="flex-1">
            <Label className="text-text-secondary">Start Date</Label>
            <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="border-gold/30 bg-canvas text-text-primary" />
          </div>
          <div className="flex-1">
            <Label className="text-text-secondary">End Date</Label>
            <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="border-gold/30 bg-canvas text-text-primary" />
          </div>
        </div>

        <Button onClick={handleExport} disabled={exporting} className="bg-gold text-black hover:bg-gold/90">
          {exporting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Download className="w-4 h-4 mr-1" />}
          Export
        </Button>

        {message && (
          <div className="flex items-center gap-2 rounded-md border border-green-500/30 bg-green-500/10 p-3 text-sm text-green-300">
            <CheckCircle2 className="w-4 h-4" /> {message}
          </div>
        )}
        {error && (
          <div className="flex items-center gap-2 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
            <AlertTriangle className="w-4 h-4" /> {error}
          </div>
        )}
      </div>
    </ModuleShell>
  );
}