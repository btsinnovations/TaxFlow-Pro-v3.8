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
import { getVendors, createVendor, updateVendor } from "@/hooks/useAPIExtensions";
import { Plus, Pencil, Loader2, AlertTriangle } from "lucide-react";

export default function VendorManager() {
  const [vendors, setVendors] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<any | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", eligible_1099: false });

  function load() {
    setLoading(true);
    getVendors()
      .then((data) => setVendors(Array.isArray(data) ? data : data?.vendors ?? []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  function openCreate() {
    setEditing(null);
    setForm({ name: "", email: "", eligible_1099: false });
    setDialogOpen(true);
  }

  function openEdit(v: any) {
    setEditing(v);
    setForm({ name: v.name ?? "", email: v.email ?? "", eligible_1099: !!v.eligible_1099 });
    setDialogOpen(true);
  }

  async function handleSave() {
    setSaving(true); setError(null);
    try {
      if (editing) await updateVendor(editing.id, form);
      else await createVendor(form);
      setDialogOpen(false);
      load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  return (
    <ModuleShell title="Vendor Manager" description="Manage vendors — create, edit, and track 1099 eligibility." moduleId="M20">
      <div className="flex items-center justify-between mb-4">
        <p className="text-text-secondary text-sm">{vendors.length} vendors</p>
        <Button onClick={openCreate} className="bg-gold text-black hover:bg-gold/90">
          <Plus className="w-4 h-4 mr-1" /> New Vendor
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
                <TableHead className="text-text-secondary">Email</TableHead>
                <TableHead className="text-text-secondary">1099 Eligible</TableHead>
                <TableHead className="text-text-secondary text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {vendors.length === 0 ? (
                <TableRow><TableCell colSpan={5} className="text-center text-text-secondary py-8">No vendors found.</TableCell></TableRow>
              ) : (
                vendors.map((v: any) => (
                  <TableRow key={v.id} className="border-divider">
                    <TableCell className="text-text-primary">{v.id}</TableCell>
                    <TableCell className="text-text-primary">{v.name}</TableCell>
                    <TableCell className="text-text-primary">{v.email ?? "—"}</TableCell>
                    <TableCell className={v.eligible_1099 ? "text-green-400" : "text-text-secondary"}>
                      {v.eligible_1099 ? "Yes" : "No"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(v)} className="text-gold hover:bg-gold/10"><Pencil className="w-3.5 h-3.5" /></Button>
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
          <DialogHeader><DialogTitle className="text-gold">{editing ? "Edit Vendor" : "New Vendor"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-text-secondary">Name</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Email</Label>
              <Input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <label className="flex items-center gap-2 text-text-secondary text-sm">
              <input type="checkbox" checked={form.eligible_1099} onChange={(e) => setForm({ ...form, eligible_1099: e.target.checked })} />
              1099 Eligible
            </label>
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