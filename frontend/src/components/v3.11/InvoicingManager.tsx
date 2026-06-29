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
  Tabs, TabsContent, TabsList, TabsTrigger,
} from "@/components/ui/tabs";
import {
  getInvoices, getBills, createInvoice, createBill, recordPayment, voidInvoice, getAging,
} from "@/hooks/useAPIExtensions";
import { Plus, DollarSign, Ban, Loader2, AlertTriangle } from "lucide-react";

export default function InvoicingManager() {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [bills, setBills] = useState<any[]>([]);
  const [aging, setAging] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogType, setDialogType] = useState<"invoice" | "bill">("invoice");
  const [payDialog, setPayDialog] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ client_id: "", vendor_id: "", amount: "", description: "", due_date: "" });
  const [payForm, setPayForm] = useState({ amount: "", date: "" });

  function load() {
    setLoading(true);
    Promise.all([getInvoices(), getBills(), getAging()])
      .then(([inv, bil, age]) => {
        setInvoices(Array.isArray(inv) ? inv : inv?.invoices ?? []);
        setBills(Array.isArray(bil) ? bil : bil?.bills ?? []);
        setAging(age);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  function openCreate(type: "invoice" | "bill") {
    setDialogType(type);
    setForm({ client_id: "", vendor_id: "", amount: "", description: "", due_date: "" });
    setDialogOpen(true);
  }

  async function handleCreate() {
    setSaving(true);
    setError(null);
    try {
      const payload = { amount: Number(form.amount), description: form.description, due_date: form.due_date, client_id: form.client_id ? Number(form.client_id) : undefined, vendor_id: form.vendor_id ? Number(form.vendor_id) : undefined };
      if (dialogType === "invoice") await createInvoice(payload);
      else await createBill(payload);
      setDialogOpen(false);
      load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  async function handlePayment() {
    if (payDialog === null) return;
    setSaving(true);
    setError(null);
    try {
      await recordPayment(payDialog, { amount: Number(payForm.amount), date: payForm.date });
      setPayDialog(null);
      setPayForm({ amount: "", date: "" });
      load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  async function handleVoid(id: number) {
    if (!confirm("Void this invoice?")) return;
    try {
      await voidInvoice(id);
      load();
    } catch (e: any) { setError(e.message); }
  }

  function renderTable(rows: any[], type: "invoice" | "bill") {
    return (
      <div className="rounded-md border border-divider overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-divider hover:bg-transparent">
              <TableHead className="text-text-secondary">ID</TableHead>
              <TableHead className="text-text-secondary">{type === "invoice" ? "Client" : "Vendor"}</TableHead>
              <TableHead className="text-text-secondary">Amount</TableHead>
              <TableHead className="text-text-secondary">Description</TableHead>
              <TableHead className="text-text-secondary">Due Date</TableHead>
              <TableHead className="text-text-secondary">Status</TableHead>
              <TableHead className="text-text-secondary text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-text-secondary py-8">No {type}s found.</TableCell>
              </TableRow>
            ) : (
              rows.map((r: any) => (
                <TableRow key={r.id} className="border-divider">
                  <TableCell className="text-text-primary">{r.id}</TableCell>
                  <TableCell className="text-text-primary">{r.client_id ?? r.vendor_id ?? "—"}</TableCell>
                  <TableCell className="text-text-primary">${(r.amount ?? 0).toLocaleString()}</TableCell>
                  <TableCell className="text-text-secondary">{r.description ?? "—"}</TableCell>
                  <TableCell className="text-text-secondary">{r.due_date ?? "—"}</TableCell>
                  <TableCell className="text-text-primary">{r.status ?? "open"}</TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm" onClick={() => { setPayDialog(r.id); setPayForm({ amount: String(r.amount ?? ""), date: new Date().toISOString().split("T")[0] }); }} className="text-gold hover:bg-gold/10">
                      <DollarSign className="w-3.5 h-3.5" />
                    </Button>
                    {type === "invoice" && (
                      <Button variant="ghost" size="sm" onClick={() => handleVoid(r.id)} className="text-red-400 hover:bg-red-500/10">
                        <Ban className="w-3.5 h-3.5" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    );
  }

  return (
    <ModuleShell title="Invoicing Manager" description="Manage invoices and bills, record payments, and view aging report." moduleId="M12">
      {loading && <div className="flex items-center gap-2 text-text-secondary"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>}
      {error && <div className="flex items-center gap-2 text-red-400 mb-4"><AlertTriangle className="w-4 h-4" /> {error}</div>}

      {aging && (
        <div className="mb-4 rounded-md border border-gold/30 bg-gold/5 p-4">
          <h3 className="text-gold text-sm font-medium mb-2">Aging Report</h3>
          <pre className="text-xs text-text-secondary whitespace-pre-wrap">{JSON.stringify(aging, null, 2).slice(0, 500)}</pre>
        </div>
      )}

      {!loading && !error && (
        <Tabs defaultValue="invoices">
          <TabsList className="bg-canvas border border-divider">
            <TabsTrigger value="invoices" className="text-text-secondary data-[state=active]:text-gold">Invoices</TabsTrigger>
            <TabsTrigger value="bills" className="text-text-secondary data-[state=active]:text-gold">Bills</TabsTrigger>
          </TabsList>
          <TabsContent value="invoices">
            <div className="flex justify-end mb-4">
              <Button onClick={() => openCreate("invoice")} className="bg-gold text-black hover:bg-gold/90">
                <Plus className="w-4 h-4 mr-1" /> New Invoice
              </Button>
            </div>
            {renderTable(invoices, "invoice")}
          </TabsContent>
          <TabsContent value="bills">
            <div className="flex justify-end mb-4">
              <Button onClick={() => openCreate("bill")} className="bg-gold text-black hover:bg-gold/90">
                <Plus className="w-4 h-4 mr-1" /> New Bill
              </Button>
            </div>
            {renderTable(bills, "bill")}
          </TabsContent>
        </Tabs>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-canvas border-divider">
          <DialogHeader>
            <DialogTitle className="text-gold">New {dialogType === "invoice" ? "Invoice" : "Bill"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {dialogType === "invoice" ? (
              <div>
                <Label className="text-text-secondary">Client ID</Label>
                <Input type="number" value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
              </div>
            ) : (
              <div>
                <Label className="text-text-secondary">Vendor ID</Label>
                <Input type="number" value={form.vendor_id} onChange={(e) => setForm({ ...form, vendor_id: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
              </div>
            )}
            <div>
              <Label className="text-text-secondary">Amount</Label>
              <Input type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div>
              <Label className="text-text-secondary">Description</Label>
              <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div>
              <Label className="text-text-secondary">Due Date</Label>
              <Input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
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

      <Dialog open={payDialog !== null} onOpenChange={(v) => !v && setPayDialog(null)}>
        <DialogContent className="bg-canvas border-divider">
          <DialogHeader>
            <DialogTitle className="text-gold">Record Payment</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-text-secondary">Amount</Label>
              <Input type="number" value={payForm.amount} onChange={(e) => setPayForm({ ...payForm, amount: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div>
              <Label className="text-text-secondary">Date</Label>
              <Input type="date" value={payForm.date} onChange={(e) => setPayForm({ ...payForm, date: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPayDialog(null)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handlePayment} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}
              Record
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ModuleShell>
  );
}