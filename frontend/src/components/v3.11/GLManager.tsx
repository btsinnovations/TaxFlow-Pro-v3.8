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
  getGlAccounts, createGlAccount, getGlEntries, postGlEntry, postAdjustingEntry, autoPostBatch,
} from "@/hooks/useAPIExtensions";
import { Plus, Zap, Loader2, AlertTriangle } from "lucide-react";

export default function GLManager() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [entryDialogOpen, setEntryDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [posting, setPosting] = useState(false);
  const [acctForm, setAcctForm] = useState({ code: "", name: "", type: "asset" });
  const [entryForm, setEntryForm] = useState({ account_id: "", debit: "", credit: "", description: "", adjusting: false });

  function load() {
    setLoading(true);
    Promise.all([getGlAccounts(), getGlEntries()])
      .then(([accts, ents]) => {
        setAccounts(Array.isArray(accts) ? accts : accts?.accounts ?? []);
        setEntries(Array.isArray(ents) ? ents : ents?.entries ?? []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function handleCreateAccount() {
    setSaving(true);
    setError(null);
    try {
      await createGlAccount(acctForm);
      setDialogOpen(false);
      setAcctForm({ code: "", name: "", type: "asset" });
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handlePostEntry() {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        account_id: Number(entryForm.account_id),
        debit: entryForm.debit ? Number(entryForm.debit) : 0,
        credit: entryForm.credit ? Number(entryForm.credit) : 0,
        description: entryForm.description,
      };
      if (entryForm.adjusting) {
        await postAdjustingEntry(payload);
      } else {
        await postGlEntry(payload);
      }
      setEntryDialogOpen(false);
      setEntryForm({ account_id: "", debit: "", credit: "", description: "", adjusting: false });
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleAutoPost() {
    setPosting(true);
    setError(null);
    try {
      await autoPostBatch();
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setPosting(false);
    }
  }

  return (
    <ModuleShell title="General Ledger" description="Manage GL accounts, post entries, and auto-post batches." moduleId="M09">
      <div className="flex items-center justify-between mb-4">
        <p className="text-text-secondary text-sm">{accounts.length} accounts · {entries.length} entries</p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleAutoPost} disabled={posting} className="border-gold/30 text-gold hover:bg-gold/10">
            {posting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Zap className="w-4 h-4 mr-1" />}
            Auto-Post Batch
          </Button>
          <Button onClick={() => setEntryDialogOpen(true)} variant="outline" className="border-gold/30 text-gold hover:bg-gold/10">
            <Plus className="w-4 h-4 mr-1" /> Post Entry
          </Button>
          <Button onClick={() => setDialogOpen(true)} className="bg-gold text-black hover:bg-gold/90">
            <Plus className="w-4 h-4 mr-1" /> New Account
          </Button>
        </div>
      </div>

      {loading && <div className="flex items-center gap-2 text-text-secondary"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>}
      {error && <div className="flex items-center gap-2 text-red-400 mb-4"><AlertTriangle className="w-4 h-4" /> {error}</div>}

      {!loading && !error && (
        <>
          <h3 className="text-text-primary font-medium mb-2">GL Accounts</h3>
          <div className="rounded-md border border-divider overflow-hidden mb-6">
            <Table>
              <TableHeader>
                <TableRow className="border-divider hover:bg-transparent">
                  <TableHead className="text-text-secondary">Code</TableHead>
                  <TableHead className="text-text-secondary">Name</TableHead>
                  <TableHead className="text-text-secondary">Type</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center text-text-secondary py-8">No accounts found.</TableCell>
                  </TableRow>
                ) : (
                  accounts.map((a: any) => (
                    <TableRow key={a.id} className="border-divider">
                      <TableCell className="text-text-primary font-mono">{a.code}</TableCell>
                      <TableCell className="text-text-primary">{a.name}</TableCell>
                      <TableCell className="text-text-primary">{a.type}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <h3 className="text-text-primary font-medium mb-2">GL Entries</h3>
          <div className="rounded-md border border-divider overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="border-divider hover:bg-transparent">
                  <TableHead className="text-text-secondary">ID</TableHead>
                  <TableHead className="text-text-secondary">Account</TableHead>
                  <TableHead className="text-text-secondary">Debit</TableHead>
                  <TableHead className="text-text-secondary">Credit</TableHead>
                  <TableHead className="text-text-secondary">Description</TableHead>
                  <TableHead className="text-text-secondary">Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-text-secondary py-8">No entries found.</TableCell>
                  </TableRow>
                ) : (
                  entries.map((e: any) => (
                    <TableRow key={e.id} className="border-divider">
                      <TableCell className="text-text-primary">{e.id}</TableCell>
                      <TableCell className="text-text-primary">{e.account_id}</TableCell>
                      <TableCell className="text-text-primary">{e.debit ? `$${Number(e.debit).toLocaleString()}` : "—"}</TableCell>
                      <TableCell className="text-text-primary">{e.credit ? `$${Number(e.credit).toLocaleString()}` : "—"}</TableCell>
                      <TableCell className="text-text-secondary">{e.description ?? "—"}</TableCell>
                      <TableCell className="text-text-secondary">{e.date ?? e.created_at ?? "—"}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-canvas border-divider">
          <DialogHeader>
            <DialogTitle className="text-gold">New GL Account</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-text-secondary">Code</Label>
              <Input value={acctForm.code} onChange={(e) => setAcctForm({ ...acctForm, code: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div>
              <Label className="text-text-secondary">Name</Label>
              <Input value={acctForm.name} onChange={(e) => setAcctForm({ ...acctForm, name: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div>
              <Label className="text-text-secondary">Type</Label>
              <select value={acctForm.type} onChange={(e) => setAcctForm({ ...acctForm, type: e.target.value })} className="w-full rounded-md border border-gold/30 bg-canvas text-text-primary p-2">
                <option value="asset">Asset</option>
                <option value="liability">Liability</option>
                <option value="equity">Equity</option>
                <option value="revenue">Revenue</option>
                <option value="expense">Expense</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handleCreateAccount} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={entryDialogOpen} onOpenChange={setEntryDialogOpen}>
        <DialogContent className="bg-canvas border-divider">
          <DialogHeader>
            <DialogTitle className="text-gold">Post GL Entry</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-text-secondary">Account</Label>
              <select value={entryForm.account_id} onChange={(e) => setEntryForm({ ...entryForm, account_id: e.target.value })} className="w-full rounded-md border border-gold/30 bg-canvas text-text-primary p-2">
                <option value="">Select account...</option>
                {accounts.map((a: any) => (
                  <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                ))}
              </select>
            </div>
            <div className="flex gap-4">
              <div className="flex-1">
                <Label className="text-text-secondary">Debit</Label>
                <Input type="number" value={entryForm.debit} onChange={(e) => setEntryForm({ ...entryForm, debit: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
              </div>
              <div className="flex-1">
                <Label className="text-text-secondary">Credit</Label>
                <Input type="number" value={entryForm.credit} onChange={(e) => setEntryForm({ ...entryForm, credit: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
              </div>
            </div>
            <div>
              <Label className="text-text-secondary">Description</Label>
              <Input value={entryForm.description} onChange={(e) => setEntryForm({ ...entryForm, description: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <label className="flex items-center gap-2 text-text-secondary text-sm">
              <input type="checkbox" checked={entryForm.adjusting} onChange={(e) => setEntryForm({ ...entryForm, adjusting: e.target.checked })} />
              Adjusting entry
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEntryDialogOpen(false)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handlePostEntry} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}
              Post
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ModuleShell>
  );
}