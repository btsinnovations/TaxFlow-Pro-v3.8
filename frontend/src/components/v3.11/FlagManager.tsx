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
import { getFlags, createFlag, resolveFlag, deleteFlag } from "@/hooks/useAPIExtensions";
import { Plus, Check, Trash2, Loader2, AlertTriangle } from "lucide-react";

export default function FlagManager() {
  const [flags, setFlags] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  function load() {
    setLoading(true);
    getFlags()
      .then((data) => setFlags(Array.isArray(data) ? data : data?.flags ?? []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function handleCreate() {
    setSaving(true);
    setError(null);
    try {
      await createFlag({ note });
      setDialogOpen(false);
      setNote("");
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleResolve(id: number) {
    try {
      await resolveFlag(id);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this flag?")) return;
    try {
      await deleteFlag(id);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <ModuleShell title="Flag Manager" description="Create and manage review flags for transactions and entries." moduleId="M08">
      <div className="flex items-center justify-between mb-4">
        <p className="text-text-secondary text-sm">{flags.length} flags</p>
        <Button onClick={() => setDialogOpen(true)} className="bg-gold text-black hover:bg-gold/90">
          <Plus className="w-4 h-4 mr-1" /> New Flag
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
                <TableHead className="text-text-secondary">Note</TableHead>
                <TableHead className="text-text-secondary">Resolved</TableHead>
                <TableHead className="text-text-secondary">Created</TableHead>
                <TableHead className="text-text-secondary text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {flags.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-text-secondary py-8">No flags found.</TableCell>
                </TableRow>
              ) : (
                flags.map((f: any) => (
                  <TableRow key={f.id} className="border-divider">
                    <TableCell className="text-text-primary">{f.id}</TableCell>
                    <TableCell className="text-text-primary">{f.note ?? "—"}</TableCell>
                    <TableCell className={f.resolved ? "text-green-400" : "text-yellow-400"}>
                      {f.resolved ? "Yes" : "No"}
                    </TableCell>
                    <TableCell className="text-text-secondary">{f.created_at ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      {!f.resolved && (
                        <Button variant="ghost" size="sm" onClick={() => handleResolve(f.id)} className="text-green-400 hover:bg-green-500/10">
                          <Check className="w-3.5 h-3.5" />
                        </Button>
                      )}
                      <Button variant="ghost" size="sm" onClick={() => handleDelete(f.id)} className="text-red-400 hover:bg-red-500/10">
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
            <DialogTitle className="text-gold">New Flag</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-text-secondary">Note</Label>
              <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Describe the issue..." className="border-gold/30 bg-canvas text-text-primary" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handleCreate} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ModuleShell>
  );
}