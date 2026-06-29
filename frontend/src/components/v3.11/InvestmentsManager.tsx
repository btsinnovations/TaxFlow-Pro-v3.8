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
  createInvestmentLot, getInvestmentHoldings, recordDividend, recordSplit, sellInvestment, getUnrealized, getCostBasis,
} from "@/hooks/useAPIExtensions";
import { Plus, TrendingUp, GitBranch, DollarSign, Loader2, AlertTriangle } from "lucide-react";

export default function InvestmentsManager() {
  const [accountId, setAccountId] = useState("1");
  const [holdings, setHoldings] = useState<any[]>([]);
  const [unrealized, setUnrealized] = useState<any | null>(null);
  const [costBasis, setCostBasis] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lotDialog, setLotDialog] = useState(false);
  const [actionDialog, setActionDialog] = useState<"dividend" | "split" | "sell" | null>(null);
  const [saving, setSaving] = useState(false);
  const [lotForm, setLotForm] = useState({ symbol: "", shares: "", cost_per_share: "", acquired: "" });
  const [actionForm, setActionForm] = useState({ shares: "", amount: "", price_per_share: "", date: "" });

  function load() {
    if (!accountId) return;
    setLoading(true);
    Promise.all([getInvestmentHoldings(Number(accountId)), getUnrealized(Number(accountId)), getCostBasis(Number(accountId))])
      .then(([h, u, c]) => {
        setHoldings(Array.isArray(h) ? h : h?.holdings ?? []);
        setUnrealized(u);
        setCostBasis(c);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, [accountId]);

  async function handleCreateLot() {
    setSaving(true);
    setError(null);
    try {
      await createInvestmentLot({
        account_id: Number(accountId),
        symbol: lotForm.symbol,
        shares: Number(lotForm.shares),
        cost_per_share: Number(lotForm.cost_per_share),
        date_acquired: lotForm.acquired,
      });
      setLotDialog(false);
      setLotForm({ symbol: "", shares: "", cost_per_share: "", acquired: "" });
      load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  async function handleAction() {
    if (!actionDialog) return;
    setSaving(true);
    setError(null);
    try {
      const payload: any = { ...actionForm, shares: Number(actionForm.shares), amount: Number(actionForm.amount), price_per_share: Number(actionForm.price_per_share) };
      if (actionDialog === "dividend") await recordDividend(Number(accountId), payload);
      if (actionDialog === "split") await recordSplit(Number(accountId), payload);
      if (actionDialog === "sell") await sellInvestment(Number(accountId), payload);
      setActionDialog(null);
      setActionForm({ shares: "", amount: "", price_per_share: "", date: "" });
      load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  return (
    <ModuleShell title="Investments Manager" description="Track holdings, record dividends/splits, and manage cost basis." moduleId="M11">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Label className="text-text-secondary">Account ID</Label>
          <Input value={accountId} onChange={(e) => setAccountId(e.target.value)} className="w-24 border-gold/30 bg-canvas text-text-primary" />
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button variant="outline" onClick={() => setActionDialog("dividend")} className="border-gold/30 text-gold hover:bg-gold/10">
            <DollarSign className="w-4 h-4 mr-1" /> Dividend
          </Button>
          <Button variant="outline" onClick={() => setActionDialog("split")} className="border-gold/30 text-gold hover:bg-gold/10">
            <GitBranch className="w-4 h-4 mr-1" /> Split
          </Button>
          <Button variant="outline" onClick={() => setActionDialog("sell")} className="border-gold/30 text-gold hover:bg-gold/10">
            <TrendingUp className="w-4 h-4 mr-1" /> Sell
          </Button>
          <Button onClick={() => setLotDialog(true)} className="bg-gold text-black hover:bg-gold/90">
            <Plus className="w-4 h-4 mr-1" /> New Lot
          </Button>
        </div>
      </div>

      {loading && <div className="flex items-center gap-2 text-text-secondary"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>}
      {error && <div className="flex items-center gap-2 text-red-400 mb-4"><AlertTriangle className="w-4 h-4" /> {error}</div>}

      {!loading && !error && (
        <>
          <h3 className="text-text-primary font-medium mb-2">Holdings</h3>
          <div className="rounded-md border border-divider overflow-hidden mb-6">
            <Table>
              <TableHeader>
                <TableRow className="border-divider hover:bg-transparent">
                  <TableHead className="text-text-secondary">Symbol</TableHead>
                  <TableHead className="text-text-secondary">Shares</TableHead>
                  <TableHead className="text-text-secondary">Cost/Share</TableHead>
                  <TableHead className="text-text-secondary">Acquired</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {holdings.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center text-text-secondary py-8">No holdings found.</TableCell>
                  </TableRow>
                ) : (
                  holdings.map((h: any, i: number) => (
                    <TableRow key={i} className="border-divider">
                      <TableCell className="text-text-primary">{h.symbol ?? "—"}</TableCell>
                      <TableCell className="text-text-primary">{h.shares ?? "—"}</TableCell>
                      <TableCell className="text-text-primary">{h.cost_per_share != null ? `$${Number(h.cost_per_share).toFixed(2)}` : "—"}</TableCell>
                      <TableCell className="text-text-secondary">{h.date_acquired ?? h.acquired ?? "—"}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {unrealized && (
              <div className="rounded-md border border-divider p-4">
                <h4 className="text-gold text-sm font-medium mb-2">Unrealized Gains/Losses</h4>
                <pre className="text-xs text-text-secondary whitespace-pre-wrap">{JSON.stringify(unrealized, null, 2).slice(0, 500)}</pre>
              </div>
            )}
            {costBasis && (
              <div className="rounded-md border border-divider p-4">
                <h4 className="text-gold text-sm font-medium mb-2">Cost Basis</h4>
                <pre className="text-xs text-text-secondary whitespace-pre-wrap">{JSON.stringify(costBasis, null, 2).slice(0, 500)}</pre>
              </div>
            )}
          </div>
        </>
      )}

      <Dialog open={lotDialog} onOpenChange={setLotDialog}>
        <DialogContent className="bg-canvas border-divider">
          <DialogHeader>
            <DialogTitle className="text-gold">New Investment Lot</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-text-secondary">Symbol</Label>
              <Input value={lotForm.symbol} onChange={(e) => setLotForm({ ...lotForm, symbol: e.target.value })} placeholder="e.g. AAPL" className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            <div className="flex gap-4">
              <div className="flex-1">
                <Label className="text-text-secondary">Shares</Label>
                <Input type="number" value={lotForm.shares} onChange={(e) => setLotForm({ ...lotForm, shares: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
              </div>
              <div className="flex-1">
                <Label className="text-text-secondary">Cost/Share</Label>
                <Input type="number" value={lotForm.cost_per_share} onChange={(e) => setLotForm({ ...lotForm, cost_per_share: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
              </div>
            </div>
            <div>
              <Label className="text-text-secondary">Date Acquired</Label>
              <Input type="date" value={lotForm.acquired} onChange={(e) => setLotForm({ ...lotForm, acquired: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setLotDialog(false)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handleCreateLot} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={actionDialog !== null} onOpenChange={(v) => !v && setActionDialog(null)}>
        <DialogContent className="bg-canvas border-divider">
          <DialogHeader>
            <DialogTitle className="text-gold capitalize">{actionDialog} Action</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-text-secondary">Shares</Label>
              <Input type="number" value={actionForm.shares} onChange={(e) => setActionForm({ ...actionForm, shares: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
            {actionDialog === "dividend" && (
              <div>
                <Label className="text-text-secondary">Amount</Label>
                <Input type="number" value={actionForm.amount} onChange={(e) => setActionForm({ ...actionForm, amount: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
              </div>
            )}
            {(actionDialog === "sell" || actionDialog === "split") && (
              <div>
                <Label className="text-text-secondary">Price/Share (sell) or Ratio (split)</Label>
                <Input type="number" value={actionForm.price_per_share} onChange={(e) => setActionForm({ ...actionForm, price_per_share: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
              </div>
            )}
            <div>
              <Label className="text-text-secondary">Date</Label>
              <Input type="date" value={actionForm.date} onChange={(e) => setActionForm({ ...actionForm, date: e.target.value })} className="border-gold/30 bg-canvas text-text-primary" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setActionDialog(null)} className="border-divider text-text-secondary">Cancel</Button>
            <Button onClick={handleAction} disabled={saving} className="bg-gold text-black hover:bg-gold/90">
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-1" />}
              Execute
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ModuleShell>
  );
}