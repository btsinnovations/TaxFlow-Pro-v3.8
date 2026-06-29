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
  getLoanSchedules, createLoanSchedule, recordLoanPayment, getCreditLines, createCreditLine, drawCreditLine, payCreditLine,
} from "@/hooks/useAPIExtensions";
import { Plus, DollarSign, CreditCard, Loader2, AlertTriangle } from "lucide-react";

export default function LiabilitiesManager() {
  const [schedules, setSchedules] = useState<any[]>([]);
  const [creditLines, setCreditLines] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loanDialog, setLoanDialog] = useState(false);
  const [creditDialog, setCreditDialog] = useState(false);
  const [payDialog, setPayDialog] = useState<number | null>(null);
  const [drawDialog, setDrawDialog] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  const [loanForm, setLoanForm] = useState({ principal: "", rate: "", term_months: "", start_date: "" });
  const [creditForm, setCreditForm] = useState({ name: "", limit: "", rate: "" });
  const [payForm, setPayForm] = useState({ amount: "", date: "" });
  const [drawForm, setDrawForm] = useState({ amount: "", description: "" });

  function load() {
    setLoading(true);
    Promise.all([getLoanSchedules(), getCreditLines()])
      .then(([sch, cl]) => {
        setSchedules(Array.isArray(sch) ? sch : sch?.schedules ?? []);
        setCreditLines(Array.isArray(cl) ? cl : cl?.credit_lines ?? []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function handleCreateLoan() {
    setSaving(true); setError(null);
    try {
      await createLoanSchedule({
        principal: Number(loanForm.principal),
        rate: Number(loanForm.rate),
        term_months: Number(loanForm.term_months),
        start_date: loanForm.start_date,
      });
      setLoanDialog(false);
      setLoanForm({ principal: "", rate: "", term_months: "", start_date: "" });
      load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  async function handleCreateCredit() {
    setSaving(true); setError(null);
    try {
      await createCreditLine({
        name: creditForm.name,
        limit: Number(creditForm.limit),
        rate: Number(creditForm.rate),
      });
      setCreditDialog(false);
      setCreditForm({ name: "", limit: "", rate: "" });
      load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  async function handleLoanPayment() {
    if (payDialog === null) return;
    setSaving(true); setError(null);
    try {
      await recordLoanPayment(payDialog, { amount: Number(payForm.amount), date: payForm.date });
      setPayDialog(null);
      setPayForm({ amount: "", date: "" });
      load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  async function handleDraw() {
    if (drawDialog === null) return;
    setSaving(true); setError(null);
    try {
      await drawCreditLine(drawDialog, { amount: Number(drawForm.amount), description: drawForm.description });
      setDrawDialog(null);
      setDrawForm({ amount: "", description: "" });
      load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  async function handlePayCredit(id: number) {
    const amt = prompt("Payment amount:");
    if (!amt) return;
    try {
      await payCreditLine(id, { amount: Number(amt) });
      load();
    } catch (e: any) { setError(e.message); }
  }

  return (
    <ModuleShell title="Liabilities Manager" description="Manage loan schedules, record payments, and track credit lines." moduleId="M13">
      {loading && <div className="flex items-center gap-2 text-text-secondary"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>}
      {error && <div className="flex items-center gap-2 text-red-400 mb-4"><AlertTriangle className="w-4 h-4" /> {error}</div>}

      {!loading && !error && (
        <Tabs defaultValue="loans">
          <TabsList className="bg-canvas border border-divider">
            <TabsTrigger value="loans" className="text-text-secondary data-[state=active]:text-gold">Loan Schedules</TabsTrigger>
            <TabsTrigger value="credit" className="text-text-secondary data-[state=active]:text-gold">Credit Lines</TabsTrigger>
          </TabsList>
          <TabsContent value="loans">
            <div className="flex justify-end mb-4">
              <Button onClick={() => setLoanDialog(true)} className="bg-gold text-black hover:bg-gold/90">
                <Plus className="w-4 h-4 mr-1" /> New Schedule
              </Button>
            </div>
            <div className="rounded-md border border-divider overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="border-divider hover:bg-transparent">
                    <TableHead className="text-text-secondary">ID</TableHead>
                    <TableHead className="text-text-secondary">Principal</TableHead>
                    <TableHead className="text-text-secondary">Rate</TableHead>
                    <TableHead className="text-text-secondary">Term</TableHead>
                    <TableHead className="text-text-secondary">Start</TableHead>
                    <TableHead className="text-text-secondary text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {schedules.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-text-secondary py-8">No loan schedules found.</TableCell>
                    </TableRow>
                  ) : (
                    schedules.map((s: any) => (
                      <TableRow key={s.id} className="border-divider">
                        <TableCell className="text-text-primary">{s.id}</TableCell>
                        <TableCell className="text-text-primary">${(s.principal ?? 0).toLocaleString()}</TableCell>
                        <TableCell className="text-text-primary">{s.rate ?? "—"}%</TableCell>
                        <TableCell className="text-text-primary">{s.term_months ?? "—"} months</TableCell>
                        <TableCell className="text-text-secondary">{s.start_date ?? "—"}</TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm" onClick={() => { setPayDialog(s.id); setPayForm({ amount: "", date: new Date().toISOString().split("T")[0] }); }} className="text-gold hover:bg-gold/10">
                            <DollarSign className="w-3.5 h-3.5" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </TabsContent>
          <TabsContent value="credit">
            <div className="flex justify-end mb-4">
              <Button onClick={() => setCreditDialog(true)} className="bg-gold text-black hover:bg-gold/90">
                <Plus className="w-4 h-4 mr-1" /> New Credit Line
              </Button>
            </div>
            <div className="rounded-md border border-divider overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="border-divider hover:bg-transparent">
                    <TableHead className="text-text-secondary">ID</TableHead>
                    <TableHead className="text-text-secondary">Name</TableHead>
                    <TableHead className="text-text-secondary">Limit</TableHead>
                    <TableHead className="text-text-secondary">Rate</TableHead>
                    <TableHead className="text-text-secondary text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {creditLines.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-text-secondary py-8">No credit lines found.</TableCell>
                    </TableRow>
                  ) : (
                    creditLines.map((cl: any) => (
                      <TableRow key={cl.id} className="border-divider">
                        <TableCell className="text-text-primary">{cl.id}</TableCell>
                        <TableCell className="text-text-primary">{cl.name ?? "—"}</TableCell>
                        <TableCell className="text-text-primary">${(cl.limit ?? 0).toLocaleString()}</TableCell>
                        <TableCell className="text-text-primary">{cl.rate ?? "—"}%</TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm" onClick={() => setDrawDialog(cl.id)} className="text-gold hover:bg-gold/10">
                            <CreditCard className="w-3.5 h-3.5" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handlePayCredit(cl.id)} className="text-green-400 hover:bg-green-500/10">
                            <DollarSign className="w-3.5 h-3.5" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </TabsContent>
        </Tabs>
      )}

      {/* Loan schedule dialog */}
      <Dialog open={loanDialog} onOpenChange={setLoanDialog}>
        <DialogContent className="bg-canvas border-divider">
          <DialogHeader>
            <DialogTitle className="text-gold">New Loan Schedule</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-text-secondary">Principal</Label>
              <Input type="number" value={loanForm.principal} onChange={(e) => setLoanForm({ ...loanForm, principal: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Rate (%)</Label>
              <Input type="number" value={loanForm.rate} onChange={(e) => setLoanForm({ ...loanForm, rate: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Term (months)</Label>
              <Input type="number" value={loanForm.term_months} onChange={(e) => setLoanForm({ ...loanForm, term_months: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Start Date</Label>
              <Input type="date" value={loanForm.start_date} onChange={(e) => setLoanForm({ ...loanForm, start_date: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setLoanDialog(false)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handleCreateLoan} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Credit line dialog */}
      <Dialog open={creditDialog} onOpenChange={setCreditDialog}>
        <DialogContent className="bg-canvas border-divider">
          <DialogHeader>
            <DialogTitle className="text-gold">New Credit Line</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-text-secondary">Name</Label>
              <Input value={creditForm.name} onChange={(e) => setCreditForm({ ...creditForm, name: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Limit</Label>
              <Input type="number" value={creditForm.limit} onChange={(e) => setCreditForm({ ...creditForm, limit: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Rate (%)</Label>
              <Input type="number" value={creditForm.rate} onChange={(e) => setCreditForm({ ...creditForm, rate: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreditDialog(false)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handleCreateCredit} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Loan payment dialog */}
      <Dialog open={payDialog !== null} onOpenChange={(v) => !v && setPayDialog(null)}>
        <DialogContent className="bg-canvas border-divider">
          <DialogHeader><DialogTitle className="text-gold">Record Loan Payment</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-text-secondary">Amount</Label>
              <Input type="number" value={payForm.amount} onChange={(e) => setPayForm({ ...payForm, amount: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Date</Label>
              <Input type="date" value={payForm.date} onChange={(e) => setPayForm({ ...payForm, date: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPayDialog(null)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handleLoanPayment} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}Record
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Draw dialog */}
      <Dialog open={drawDialog !== null} onOpenChange={(v) => !v && setDrawDialog(null)}>
        <DialogContent className="bg-canvas border-divider">
          <DialogHeader><DialogTitle className="text-gold">Draw on Credit Line</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label className="text-text-secondary">Amount</Label>
              <Input type="number" value={drawForm.amount} onChange={(e) => setDrawForm({ ...drawForm, amount: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
            <div><Label className="text-text-secondary">Description</Label>
              <Input value={drawForm.description} onChange={(e) => setDrawForm({ ...drawForm, description: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDrawDialog(null)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handleDraw} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}Draw
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ModuleShell>
  );
}