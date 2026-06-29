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
import { getRules, createRule, updateRule, deleteRule } from "@/hooks/useAPIExtensions";
import { Plus, Pencil, Trash2, Loader2, AlertTriangle } from "lucide-react";

export default function RuleManager() {
  const [rules, setRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<any | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", pattern: "", category: "", account_id: "" });

  function load() {
    setLoading(true);
    getRules()
      .then((data) => setRules(Array.isArray(data) ? data : data?.rules ?? []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  function openCreate() {
    setEditing(null);
    setForm({ name: "", pattern: "", category: "", account_id: "" });
    setDialogOpen(true);
  }

  function openEdit(r: any) {
    setEditing(r);
    setForm({ name: r.name ?? "", pattern: r.pattern ?? "", category: r.category ?? "", account_id: String(r.account_id ?? "") });
    setDialogOpen(true);
  }

  async function handleSave() {
    setSaving(true); setError(null);
    try {
      const payload = { ...form, account_id: form.account_id ? Number(form.account_id) : undefined };
      if (editing) await updateRule(editing.id, payload);
      else await createRule(payload);
      setDialogOpen(false);
      load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this rule?")) return;
    try { await deleteRule(id); load(); } catch (e: any) { setError(e.message); }
  }

  return (
    <ModuleShell title="Categorization Rules" description="Manage automatic transaction categorization rules." moduleId="M16">
      <div className="flex items-center justify-between mb-4">
        <p className="text-text-secondary text-sm">{rules.length} rules</p>
        <Button onClick={openCreate} className="bg-gold text-black hover:bg-gold/90">
          <Plus className="w-4 h-4 mr-1" /> New Rule
        </Button>
      </div>

      {loading && <div className="flex items-center gap-2 text-text-secondary"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>}
      {error && <div className="flex items-center gap-2 text-red-400 mb-4"><AlertTriangle className="w-4 h-4" /> {error}</div>}

      {!loading && !error && (
        <div className="rounded-md border border-divider overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="border-divider hover:bg-transparent">
                <TableHead className="text-text-secondary">ID</TableHead>
                <TableHead className="text-text-secondary">Name</TableHead>
                <TableHead className="text-text-secondary">Pattern</TableHead>
                <TableHead className="text-text-secondary">Category</TableHead>
                <TableHead className="text-text-secondary">Account</TableHead>
                <TableHead className="text-text-secondary text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-text-secondary py-8">No rules found.</TableCell>
                </TableRow>
              ) : (
                rules.map((r: any) => (
                  <TableRow key={r.id} className="border-divider">
                    <TableCell className="text-text-primary">{r.id}</TableCell>
                    <TableCell className="text-text-primary">{r.name}</TableCell>
                    <TableCell className="text-text-secondary font-mono">{r.pattern ?? "—"}</TableCell>
                    <TableCell className="text-text-primary">{r.category ?? "—"}</TableCell>
                    <TableCell className="text-text-primary">{r.account_id ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(r)} className="text-gold hover:bg-gold/10"><Pencil className="w-3.5 h-3.5" /></Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDelete(r.id)} className="text-red-400 hover:bg-red-500/10"><Trash2 className="w-3.5 h-3.5" /></Button>
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
          <DialogHeader><DialogTitle className="text-gold">{editing ? "Edit Rule" : "New Rule"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-text-secondary">Name</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Pattern (regex or text match)</Label>
              <Input value={form.pattern} onChange={(e) => setForm({ ...form, pattern: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Category</Label>
              <Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Account ID</Label>
              <Input type="number" value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handleSave} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}{editing ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ModuleShell>
  );
}