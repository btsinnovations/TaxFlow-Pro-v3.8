import { useEffect, useState } from "react";
import ModuleShell from "./ModuleShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import { getMileageEntries, createMileageEntry, getMileageSummary } from "@/hooks/useAPIExtensions";
import { Plus, Loader2, AlertTriangle } from "lucide-react";

export default function MileageLog() {
  const [entries, setEntries] = useState<any[]>([]);
  const [summary, setSummary] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ date: "", miles: "", description: "" });

  function load() {
    setLoading(true);
    Promise.all([getMileageEntries(), getMileageSummary()])
      .then(([ent, sum]) => {
        setEntries(Array.isArray(ent) ? ent : ent?.entries ?? []);
        setSummary(sum);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function handleCreate() {
    setSaving(true); setError(null);
    try {
      await createMileageEntry({
        date: form.date,
        miles: Number(form.miles),
        description: form.description,
      });
      setDialogOpen(false);
      setForm({ date: "", miles: "", description: "" });
      load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  const totalMiles = entries.reduce((sum: number, e: any) => sum + (e.miles ?? 0), 0);

  return (
    <ModuleShell title="Mileage Log" description="Track mileage entries for tax deduction purposes." moduleId="M14">
      <div className="flex items-center justify-between mb-4">
        <p className="text-text-secondary text-sm">{entries.length} entries · {totalMiles.toFixed(1)} total miles</p>
        <Button onClick={() => setDialogOpen(true)} className="bg-gold text-black hover:bg-gold/90">
          <Plus className="w-4 h-4 mr-1" /> New Entry
        </Button>
      </div>

      {loading && <div className="flex items-center gap-2 text-text-secondary"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>}
      {error && <div className="flex items-center gap-2 text-red-400 mb-4"><AlertTriangle className="w-4 h-4" /> {error}</div>}

      {summary && (
        <Card className="bg-canvas border-divider mb-4">
          <CardHeader><CardTitle className="text-gold text-sm">Summary</CardTitle></CardHeader>
          <CardContent>
            <pre className="text-xs text-text-secondary whitespace-pre-wrap">{JSON.stringify(summary, null, 2).slice(0, 300)}</pre>
          </CardContent>
        </Card>
      )}

      {!loading && !error && (
        <div className="rounded-md border border-divider overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="border-divider hover:bg-transparent">
                <TableHead className="text-text-secondary">Date</TableHead>
                <TableHead className="text-text-secondary">Miles</TableHead>
                <TableHead className="text-text-secondary">Description</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} className="text-center text-text-secondary py-8">No mileage entries found.</TableCell>
                </TableRow>
              ) : (
                entries.map((e: any, i: number) => (
                  <TableRow key={e.id ?? i} className="border-divider">
                    <TableCell className="text-text-primary">{e.date ?? "—"}</TableCell>
                    <TableCell className="text-text-primary">{e.miles ?? "—"}</TableCell>
                    <TableCell className="text-text-secondary">{e.description ?? "—"}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-canvas border-divider">
          <DialogHeader><DialogTitle className="text-gold">New Mileage Entry</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-text-secondary">Date</Label>
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div>
              <Label className="text-text-secondary">Miles</Label>
              <Input type="number" step="0.1" value={form.miles} onChange={(e) => setForm({ ...form, miles: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div>
              <Label className="text-text-secondary">Description</Label>
              <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Business purpose..." className="border-gold/30 bg-canvas text-text-primary" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handleCreate} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ModuleShell>
  );
}