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
import { getTaxRules, updateTaxRule, getTaxSummary } from "@/hooks/useAPIExtensions";
import { Pencil, Loader2, AlertTriangle } from "lucide-react";

export default function TaxManager() {
  const [rules, setRules] = useState<any[]>([]);
  const [summary, setSummary] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<any | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", rate: "", bracket_min: "", bracket_max: "" });
  const [year, setYear] = useState(new Date().getFullYear());

  function load() {
    setLoading(true);
    Promise.all([getTaxRules(), getTaxSummary(new Date().getFullYear())])
      .then(([r, s]) => {
        setRules(Array.isArray(r) ? r : r?.rules ?? []);
        setSummary(s);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  function openEdit(r: any) {
    setEditing(r);
    setForm({ name: r.name ?? "", rate: String(r.rate ?? ""), bracket_min: String(r.bracket_min ?? ""), bracket_max: String(r.bracket_max ?? "") });
    setDialogOpen(true);
  }

  async function handleSave() {
    if (!editing) return;
    setSaving(true); setError(null);
    try {
      await updateTaxRule(editing.id, {
        name: form.name,
        rate: form.rate ? Number(form.rate) : undefined,
        bracket_min: form.bracket_min ? Number(form.bracket_min) : undefined,
        bracket_max: form.bracket_max ? Number(form.bracket_max) : undefined,
      });
      setDialogOpen(false);
      load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  async function loadSummary() {
    try {
      const s = await getTaxSummary(year);
      setSummary(s);
    } catch (e: any) { setError(e.message); }
  }

  return (
    <ModuleShell title="Tax Manager" description="Manage tax rules and view tax summaries by year." moduleId="M18">
      {loading && <div className="flex items-center gap-2 text-text-secondary"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>}
      {error && <div className="flex items-center gap-2 text-red-400 mb-4"><AlertTriangle className="w-4 h-4" /> {error}</div>}

      {summary && (
        <Card className="bg-canvas border-divider mb-6">
          <CardHeader>
            <CardTitle className="text-gold text-sm flex items-center gap-2">
              Tax Summary —
              <Input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} onBlur={loadSummary} className="w-20 border-gold/30 bg-canvas text-text-primary" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs text-text-secondary whitespace-pre-wrap">{JSON.stringify(summary, null, 2).slice(0, 500)}</pre>
          </CardContent>
        </Card>
      )}

      {!loading && !error && (
        <div className="rounded-md border border-divider overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="border-divider hover:bg-transparent">
                <TableHead className="text-text-secondary">ID</TableHead>
                <TableHead className="text-text-secondary">Name</TableHead>
                <TableHead className="text-text-secondary">Rate</TableHead>
                <TableHead className="text-text-secondary">Bracket Min</TableHead>
                <TableHead className="text-text-secondary">Bracket Max</TableHead>
                <TableHead className="text-text-secondary text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.length === 0 ? (
                <TableRow><TableCell colSpan={6} className="text-center text-text-secondary py-8">No tax rules found.</TableCell></TableRow>
              ) : (
                rules.map((r: any) => (
                  <TableRow key={r.id} className="border-divider">
                    <TableCell className="text-text-primary">{r.id}</TableCell>
                    <TableCell className="text-text-primary">{r.name}</TableCell>
                    <TableCell className="text-text-primary">{r.rate ?? "—"}%</TableCell>
                    <TableCell className="text-text-primary">{r.bracket_min != null ? `$${r.bracket_min.toLocaleString()}` : "—"}</TableCell>
                    <TableCell className="text-text-primary">{r.bracket_max != null ? `$${r.bracket_max.toLocaleString()}` : "—"}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(r)} className="text-gold hover:bg-gold/10"><Pencil className="w-3.5 h-3.5" /></Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-canvas border-divider">
          <DialogHeader><DialogTitle className="text-gold">Edit Tax Rule</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-text-secondary">Name</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Rate (%)</Label>
              <Input type="number" step="0.01" value={form.rate} onChange={(e) => setForm({ ...form, rate: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div className="flex gap-4">
              <div className="flex-1"><Label className="text-text-secondary">Bracket Min</Label>
                <Input type="number" value={form.bracket_min} onChange={(e) => setForm({ ...form, bracket_min: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
              <div className="flex-1"><Label className="text-text-secondary">Bracket Max</Label>
                <Input type="number" value={form.bracket_max} onChange={(e) => setForm({ ...form, bracket_max: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handleSave} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}Update
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ModuleShell>
  );
}