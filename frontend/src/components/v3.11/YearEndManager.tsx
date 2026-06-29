import { useState } from "react";
import ModuleShell from "./ModuleShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { runYearEndClose, getYearEndPackage } from "@/hooks/useAPIExtensions";
import { Loader2, AlertTriangle, CheckCircle2, Download, CalendarClock } from "lucide-react";

export default function YearEndManager() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [closing, setClosing] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleClose() {
    if (!confirm(`Run year-end close for ${year}? This is a significant operation.`)) return;
    setClosing(true);
    setError(null);
    setMessage(null);
    try {
      const res = await runYearEndClose({ year });
      setMessage(`Year-end close complete: ${JSON.stringify(res).slice(0, 300)}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setClosing(false);
    }
  }

  async function handleDownload() {
    setDownloading(true);
    setError(null);
    setMessage(null);
    try {
      const blob = await getYearEndPackage();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `year-end-${year}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      setMessage("Year-end package downloaded.");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <ModuleShell title="Year-End Manager" description="Run year-end close and download year-end tax packages." moduleId="M21">
      <div className="max-w-lg space-y-4">
        <div>
          <Label className="text-text-secondary">Tax Year</Label>
          <Input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} className="border-gold/30 bg-canvas text-text-primary" />
        </div>

        <div className="flex gap-2">
          <Button onClick={handleClose} disabled={closing} className="bg-gold text-black hover:bg-gold/90">
            {closing ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <CalendarClock className="w-4 h-4 mr-1" />}
            Run Year-End Close
          </Button>
          <Button onClick={handleDownload} disabled={downloading} variant="outline" className="border-gold/30 text-gold hover:bg-gold/10">
            {downloading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Download className="w-4 h-4 mr-1" />}
            Download Package
          </Button>
        </div>

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