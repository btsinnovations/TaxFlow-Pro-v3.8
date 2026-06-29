import { useEffect, useState } from "react";
import ModuleShell from "./ModuleShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import { closePeriod, reopenPeriod, getPeriodStatus } from "@/hooks/useAPIExtensions";
import { Loader2, AlertTriangle, Lock, Unlock } from "lucide-react";

export default function PeriodManager() {
  const [periodId, setPeriodId] = useState("2026-06");
  const [status, setStatus] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [acting, setActing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadStatus() {
    if (!periodId) return;
    setLoading(true);
    setError(null);
    try {
      const s = await getPeriodStatus(periodId);
      setStatus(s);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadStatus(); }, [periodId]);

  async function handleClose() {
    if (!confirm(`Close period ${periodId}?`)) return;
    setActing(true); setError(null); setMessage(null);
    try {
      await closePeriod(periodId);
      setMessage(`Period ${periodId} closed.`);
      loadStatus();
    } catch (e: any) { setError(e.message); } finally { setActing(false); }
  }

  async function handleReopen() {
    if (!confirm(`Reopen period ${periodId}?`)) return;
    setActing(true); setError(null); setMessage(null);
    try {
      await reopenPeriod(periodId);
      setMessage(`Period ${periodId} reopened.`);
      loadStatus();
    } catch (e: any) { setError(e.message); } finally { setActing(false); }
  }

  return (
    <ModuleShell title="Period Manager" description="Close and reopen accounting periods." moduleId="M15">
      <div className="max-w-lg space-y-4">
        <div>
          <Label className="text-text-secondary">Period ID</Label>
          <Input value={periodId} onChange={(e) => setPeriodId(e.target.value)} placeholder="e.g. 2026-06" className="border-gold/30 bg-canvas text-text-primary" />
        </div>

        <div className="flex gap-2">
          <Button variant="outline" onClick={loadStatus} disabled={loading} className="border-gold/30 text-gold hover:bg-gold/10">
            {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
            Check Status
          </Button>
          <Button onClick={handleClose} disabled={acting} className="bg-gold text-black hover:bg-gold/90">
            {acting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Lock className="w-4 h-4 mr-1" />}
            Close Period
          </Button>
          <Button onClick={handleReopen} disabled={acting} variant="outline" className="border-gold/30 text-gold hover:bg-gold/10">
            {acting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Unlock className="w-4 h-4 mr-1" />}
            Reopen Period
          </Button>
        </div>

        {message && (
          <div className="rounded-md border border-green-500/30 bg-green-500/10 p-3 text-sm text-green-300">{message}</div>
        )}
        {error && (
          <div className="flex items-center gap-2 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
            <AlertTriangle className="w-4 h-4" /> {error}
          </div>
        )}

        {status && (
          <Card className="bg-canvas border-divider">
            <CardHeader><CardTitle className="text-gold text-sm">Period Status</CardTitle></CardHeader>
            <CardContent>
              <pre className="text-xs text-text-secondary whitespace-pre-wrap">{JSON.stringify(status, null, 2)}</pre>
            </CardContent>
          </Card>
        )}
      </div>
    </ModuleShell>
  );
}