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
  getCoaAccounts, createCoaAccount, deleteCoaAccount, seedCoa, renumberCoaAccount, setCoaAccountParent,
} from "@/hooks/useAPIExtensions";
import { Plus, Trash2, Sprout, Loader2, AlertTriangle } from "lucide-react";

export default function COAManager() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", type: "asset", parent_id: "" });
  const [saving, setSaving] = useState(false);
  const [seeding, setSeeding] = useState(false);

  function load() {
    setLoading(true);
    getCoaAccounts()
      .then((data) => setAccounts(Array.isArray(data) ? data : data?.accounts ?? []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function handleCreate() {
    setSaving(true);
    setError(null);
    try {
      await createCoaAccount({
        code: form.code,
        name: form.name,
        type: form.type,
        parent_id: form.parent_id ? Number(form.parent_id) : null,
      });
      setDialogOpen(false);
      setForm({ code: "", name: "", type: "asset", parent_id: "" });
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleSeed() {
    if (!confirm("Seed default chart of accounts? This may add many accounts.")) return;
    setSeeding(true);
    setError(null);
    try {
      await seedCoa();
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSeeding(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this account?")) return;
    try {
      await deleteCoaAccount(id);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleRenumber(id: number) {
    const newCode = prompt("Enter new code:");
    if (!newCode) return;
    try {
      await renumberCoaAccount(id, { code: newCode });
      load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleSetParent(id: number) {
    const parentId = prompt("Enter parent account ID:");
    if (!parentId) return;
    try {
      await setCoaAccountParent(id, Number(parentId));
      load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <ModuleShell title="Chart of Accounts" description="Manage the chart of accounts — create, seed, renumber, and set parent accounts." moduleId="M04">
      <div className="flex items-center justify-between mb-4">
        <p className="text-text-secondary text-sm">{accounts.length} accounts</p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleSeed} disabled={seeding} className="border-gold/30 text-gold hover:bg-gold/10">
            {seeding ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Sprout className="w-4 h-4 mr-1" />}
            Seed Default
          </Button>
          <Button onClick={() => setDialogOpen(true)} className="bg-gold text-black hover:bg-gold/90">
            <Plus className="w-4 h-4 mr-1" /> New Account
          </Button>
        </div>
      </div>

      {loading && <div className="flex items-center gap-2 text-text-secondary"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>}
      {error && <div className="flex items-center gap-2 text-red-400 mb-4"><AlertTriangle className="w-4 h-4" /> {error}</div>}

      {!loading && !error && (
        <div className="rounded-md border border-divider overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="border-divider hover:bg-transparent">
                <TableHead className="text-text-secondary">Code</TableHead>
                <TableHead className="text-text-secondary">Name</TableHead>
                <TableHead className="text-text-secondary">Type</TableHead>
                <TableHead className="text-text-secondary">Parent</TableHead>
                <TableHead className="text-text-secondary text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {accounts.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-text-secondary py-8">No accounts found. Click "Seed Default" to populate.</TableCell>
                </TableRow>
              ) : (
                accounts.map((a: any) => (
                  <TableRow key={a.id} className="border-divider">
                    <TableCell className="text-text-primary font-mono">{a.code}</TableCell>
                    <TableCell className="text-text-primary">{a.name}</TableCell>
                    <TableCell className="text-text-primary">{a.type}</TableCell>
                    <TableCell className="text-text-secondary">{a.parent_id ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => handleRenumber(a.id)} className="text-gold hover:bg-gold/10 text-xs">Renumber</Button>
                      <Button variant="ghost" size="sm" onClick={() => handleSetParent(a.id)} className="text-gold hover:bg-gold/10 text-xs">Set Parent</Button>
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
            <DialogTitle className="text-gold">New Account</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-text-secondary">Code</Label>
              <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="e.g. 1000" className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div>
              <Label className="text-text-secondary">Name</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Cash" className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div>
              <Label className="text-text-secondary">Type</Label>
              <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="w-full rounded-md border border-gold/30 bg-canvas text-text-primary p-2">
                <option value="asset">Asset</option>
                <option value="liability">Liability</option>
                <option value="equity">Equity</option>
                <option value="revenue">Revenue</option>
                <option value="expense">Expense</option>
              </select>
            </div>
            <div>
              <Label className="text-text-secondary">Parent ID (optional)</Label>
              <Input value={form.parent_id} onChange={(e) => setForm({ ...form, parent_id: e.target.value })} placeholder="e.g. 1" className="border-gold/30 bg-canvas text-text-primary" />
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