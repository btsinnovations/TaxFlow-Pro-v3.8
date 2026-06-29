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
import { getClients, createClient, updateClient, deleteClient } from "@/hooks/useAPIExtensions";
import { Plus, Pencil, Trash2, Loader2, AlertTriangle } from "lucide-react";

export default function ClientManager() {
  const [clients, setClients] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<any | null>(null);
  const [form, setForm] = useState({ name: "", email: "" });
  const [saving, setSaving] = useState(false);

  function load() {
    setLoading(true);
    getClients()
      .then((data) => setClients(Array.isArray(data) ? data : data?.clients ?? []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  function openCreate() {
    setEditing(null);
    setForm({ name: "", email: "" });
    setDialogOpen(true);
  }

  function openEdit(c: any) {
    setEditing(c);
    setForm({ name: c.name ?? "", email: c.email ?? "" });
    setDialogOpen(true);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      if (editing) {
        await updateClient(editing.id, form);
      } else {
        await createClient(form);
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
    if (!confirm("Delete this client?")) return;
    try {
      await deleteClient(id);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <ModuleShell title="Client Manager" description="ManageTaxFlow Pro clients — create, edit, and delete." moduleId="M03">
      <div className="flex items-center justify-between mb-4">
        <p className="text-text-secondary text-sm">{clients.length} clients</p>
        <Button onClick={openCreate} className="bg-gold text-black hover:bg-gold/90">
          <Plus className="w-4 h-4 mr-1" /> New Client
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
                <TableHead className="text-text-secondary">Created</TableHead>
                <TableHead className="text-text-secondary text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {clients.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-text-secondary py-8">No clients found.</TableCell>
                </TableRow>
              ) : (
                clients.map((c: any) => (
                  <TableRow key={c.id} className="border-divider">
                    <TableCell className="text-text-primary">{c.id}</TableCell>
                    <TableCell className="text-text-primary">{c.name}</TableCell>
                    <TableCell className="text-text-primary">{c.email ?? "—"}</TableCell>
                    <TableCell className="text-text-secondary">{c.created_at ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(c)} className="text-gold hover:bg-gold/10">
                        <Pencil className="w-3.5 h-3.5" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDelete(c.id)} className="text-red-400 hover:bg-red-500/10">
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
            <DialogTitle className="text-gold">{editing ? "Edit Client" : "New Client"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-text-secondary">Name</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div>
              <Label className="text-text-secondary">Email</Label>
              <Input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
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