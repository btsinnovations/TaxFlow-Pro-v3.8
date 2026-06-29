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
import { getSalesTaxRates, createSalesTaxRate, getSalesTaxPayments, createSalesTaxPayment, getSalesTaxLiabilitySummary } from "@/hooks/useAPIExtensions";
import { Plus, Loader2, AlertTriangle } from "lucide-react";

export default function SalesTaxManager() {
  const [rates, setRates] = useState<any[]>([]);
  const [payments, setPayments] = useState<any[]>([]);
  const [liability, setLiability] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rateDialog, setRateDialog] = useState(false);
  const [payDialog, setPayDialog] = useState(false);
  const [saving, setSaving] = useState(false);
  const [rateForm, setRateForm] = useState({ jurisdiction: "", rate: "", effective_date: "" });
  const [payForm, setPayForm] = useState({ jurisdiction: "", amount: "", period: "" });

  function load() {
    setLoading(true);
    Promise.all([getSalesTaxRates(), getSalesTaxPayments(), getSalesTaxLiabilitySummary()])
      .then(([r, p, l]) => {
        setRates(Array.isArray(r) ? r : r?.rates ?? []);
        setPayments(Array.isArray(p) ? p : p?.payments ?? []);
        setLiability(l);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function handleCreateRate() {
    setSaving(true); setError(null);
    try {
      await createSalesTaxRate({ ...rateForm, rate: Number(rateForm.rate) });
      setRateDialog(false);
      setRateForm({ jurisdiction: "", rate: "", effective_date: "" });
      load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  async function handleCreatePayment() {
    setSaving(true); setError(null);
    try {
      await createSalesTaxPayment({ ...payForm, amount: Number(payForm.amount) });
      setPayDialog(false);
      setPayForm({ jurisdiction: "", amount: "", period: "" });
      load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  return (
    <ModuleShell title="Sales Tax Manager" description="Manage sales tax rates, payments, and view liability summaries." moduleId="M17">
      {loading && <div className="flex items-center gap-2 text-text-secondary"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>}
      {error && <div className="flex items-center gap-2 text-red-400 mb-4"><AlertTriangle className="w-4 h-4" /> {error}</div>}

      {liability && (
        <Card className="bg-canvas border-divider mb-6">
          <CardHeader><CardTitle className="text-gold text-sm">Liability Summary</CardTitle></CardHeader>
          <CardContent>
            <pre className="text-xs text-text-secondary whitespace-pre-wrap">{JSON.stringify(liability, null, 2).slice(0, 500)}</pre>
          </CardContent>
        </Card>
      )}

      {!loading && !error && (
        <>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-text-primary font-medium">Tax Rates</h3>
            <Button onClick={() => setRateDialog(true)} className="bg-gold text-black hover:bg-gold/90">
              <Plus className="w-4 h-4 mr-1" /> New Rate
            </Button>
          </div>
          <div className="rounded-md border border-divider overflow-hidden mb-6">
            <Table>
              <TableHeader>
                <TableRow className="border-divider hover:bg-transparent">
                  <TableHead className="text-text-secondary">Jurisdiction</TableHead>
                  <TableHead className="text-text-secondary">Rate</TableHead>
                  <TableHead className="text-text-secondary">Effective</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rates.length === 0 ? (
                  <TableRow><TableCell colSpan={3} className="text-center text-text-secondary py-8">No rates found.</TableCell></TableRow>
                ) : (
                  rates.map((r: any, i: number) => (
                    <TableRow key={r.id ?? i} className="border-divider">
                      <TableCell className="text-text-primary">{r.jurisdiction ?? "—"}</TableCell>
                      <TableCell className="text-text-primary">{r.rate ?? "—"}%</TableCell>
                      <TableCell className="text-text-secondary">{r.effective_date ?? "—"}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <div className="flex items-center justify-between mb-2">
            <h3 className="text-text-primary font-medium">Payments</h3>
            <Button onClick={() => setPayDialog(true)} className="bg-gold text-black hover:bg-gold/90">
              <Plus className="w-4 h-4 mr-1" /> New Payment
            </Button>
          </div>
          <div className="rounded-md border border-divider overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="border-divider hover:bg-transparent">
                  <TableHead className="text-text-secondary">Jurisdiction</TableHead>
                  <TableHead className="text-text-secondary">Amount</TableHead>
                  <TableHead className="text-text-secondary">Period</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {payments.length === 0 ? (
                  <TableRow><TableCell colSpan={3} className="text-center text-text-secondary py-8">No payments found.</TableCell></TableRow>
                ) : (
                  payments.map((p: any, i: number) => (
                    <TableRow key={p.id ?? i} className="border-divider">
                      <TableCell className="text-text-primary">{p.jurisdiction ?? "—"}</TableCell>
                      <TableCell className="text-text-primary">${(p.amount ?? 0).toLocaleString()}</TableCell>
                      <TableCell className="text-text-secondary">{p.period ?? "—"}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </>
      )}

      <Dialog open={rateDialog} onOpenChange={setRateDialog}>
        <DialogContent className="bg-canvas border-divider">
          <DialogHeader><DialogTitle className="text-gold">New Tax Rate</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-text-secondary">Jurisdiction</Label>
              <Input value={rateForm.jurisdiction} onChange={(e) => setRateForm({ ...rateForm, jurisdiction: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Rate (%)</Label>
              <Input type="number" step="0.01" value={rateForm.rate} onChange={(e) => setRateForm({ ...rateForm, rate: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Effective Date</Label>
              <Input type="date" value={rateForm.effective_date} onChange={(e) => setRateForm({ ...rateForm, effective_date: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRateDialog(false)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handleCreateRate} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={payDialog} onOpenChange={setPayDialog}>
        <DialogContent className="bg-canvas border-divider">
          <DialogHeader><DialogTitle className="text-gold">New Payment</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-text-secondary">Jurisdiction</Label>
              <Input value={payForm.jurisdiction} onChange={(e) => setPayForm({ ...payForm, jurisdiction: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Amount</Label>
              <Input type="number" value={payForm.amount} onChange={(e) => setPayForm({ ...payForm, amount: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Period</Label>
              <Input value={payForm.period} onChange={(e) => setPayForm({ ...payForm, period: e.target.value })} placeholder="e.g. 2026-Q2" className="border-gold/30 bg-canvas text-text-primary" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPayDialog(false)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handleCreatePayment} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ModuleShell>
  );
}