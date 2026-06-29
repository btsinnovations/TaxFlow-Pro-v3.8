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
import { getDepreciationAssets, createDepreciationAsset, updateDepreciationAsset, deleteDepreciationAsset } from "@/hooks/useAPIExtensions";
import { Plus, Pencil, Trash2, Loader2, AlertTriangle } from "lucide-react";

export default function DepreciationManager() {
  const [assets, setAssets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<any | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", asset_class: "", cost: "", placed_in_service: "", method: "straight-line" });

  function load() {
    setLoading(true);
    getDepreciationAssets()
      .then((data) => setAssets(Array.isArray(data) ? data : data?.assets ?? []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  function openCreate() {
    setEditing(null);
    setForm({ name: "", asset_class: "", cost: "", placed_in_service: "", method: "straight-line" });
    setDialogOpen(true);
  }

  function openEdit(a: any) {
    setEditing(a);
    setForm({
      name: a.name ?? "",
      asset_class: a.asset_class ?? a.class ?? "",
      cost: String(a.cost ?? ""),
      placed_in_service: a.placed_in_service ?? "",
      method: a.method ?? "straight-line",
    });
    setDialogOpen(true);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        ...form,
        cost: form.cost ? Number(form.cost) : 0,
      };
      if (editing) {
        await updateDepreciationAsset(editing.id, payload);
      } else {
        await createDepreciationAsset(payload);
      }
      setDialogOpen(false);
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this asset?")) return;
    try {
      await deleteDepreciationAsset(id);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <ModuleShell title="Depreciation Manager" description="Track fixed assets and depreciation schedules." moduleId="M06">
      <div className="flex items-center justify-between mb-4">
        <p className="text-text-secondary text-sm">{assets.length} assets</p>
        <Button onClick={openCreate} className="bg-gold text-black hover:bg-gold/90">
          <Plus className="w-4 h-4 mr-1" /> New Asset
        </Button>
      </div>

      {loading && <div className="flex items-center gap-2 text-text-secondary"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>}
      {error && <div className="flex items-center gap-2 text-red-400 mb-4"><AlertTriangle className="w-4 h-4" /> {error}</div>}

      {!loading && !error && (
        <div className="rounded-md border border-divider overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="border-divider hover:bg-transparent">
                <TableHead className="text-text-secondary">Name</TableHead>
                <TableHead className="text-text-secondary">Class</TableHead>
                <TableHead className="text-text-secondary">Cost</TableHead>
                <TableHead className="text-text-secondary">Placed in Service</TableHead>
                <TableHead className="text-text-secondary">Method</TableHead>
                <TableHead className="text-text-secondary text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {assets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-text-secondary py-8">No assets found.</TableCell>
                </TableRow>
              ) : (
                assets.map((a: any) => (
                  <TableRow key={a.id} className="border-divider">
                    <TableCell className="text-text-primary">{a.name}</TableCell>
                    <TableCell className="text-text-primary">{a.asset_class ?? a.class ?? "—"}</TableCell>
                    <TableCell className="text-text-primary">${(a.cost ?? 0).toLocaleString()}</TableCell>
                    <TableCell className="text-text-secondary">{a.placed_in_service ?? "—"}</TableCell>
                    <TableCell className="text-text-primary">{a.method ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(a)} className="text-gold hover:bg-gold/10">
                        <Pencil className="w-3.5 h-3.5" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDelete(a.id)} className="text-red-400 hover:bg-red-500/10">
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
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
          <DialogHeader>
            <DialogTitle className="text-gold">{editing ? "Edit Asset" : "New Asset"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-text-secondary">Name</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div>
              <Label className="text-text-secondary">Class</Label>
              <Input value={form.asset_class} onChange={(e) => setForm({ ...form, asset_class: e.target.value })} placeholder="e.g. 5-year" className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div>
              <Label className="text-text-secondary">Cost</Label>
              <Input type="number" value={form.cost} onChange={(e) => setForm({ ...form, cost: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div>
              <Label className="text-text-secondary">Placed in Service</Label>
              <Input type="date" value={form.placed_in_service} onChange={(e) => setForm({ ...form, placed_in_service: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div>
              <Label className="text-text-secondary">Method</Label>
              <select value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })} className="w-full rounded-md border border-gold/30 bg-canvas text-text-primary p-2">
                <option value="straight-line">Straight-line</option>
                <option value="double-declining">Double-declining</option>
                <option value="macrs">MACRS</option>
                <option value="units-of-production">Units of Production</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handleSave} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}
              {editing ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ModuleShell>
  );
}