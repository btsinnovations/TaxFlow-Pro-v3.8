import { useEffect, useState, useRef, useCallback } from 'react';
import { Building, Plus, Trash2, Download, AlertCircle } from 'lucide-react';
import {
  getBankConnections, createBankConnection, deleteBankConnection, fetchBankTransactions,
  getAccounts,
} from '@/hooks/useAPI';
import { useToast } from '@/hooks/useToast';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface BankConnection {
  id: number;
  institution_name: string;
  connection_type: string;
  status: string;
  ofx_username: string;
  ofx_password_masked: string;
  ofx_url: string | null;
  ofx_org: string | null;
  ofx_fid: string | null;
  routing_number: string | null;
  account_number_masked: string | null;
  last_sync: string | null;
  created_at: string;
}

export default function BankConnectionsPage() {
  const { toast } = useToast();
  const sectionRef = useRef<HTMLDivElement>(null);

  const [connections, setConnections] = useState<BankConnection[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [fetching, setFetching] = useState<number | null>(null);

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    account_id: '',
    institution_name: '',
    ofx_username: '',
    ofx_password: '',
    ofx_url: '',
    ofx_org: '',
    ofx_fid: '',
    routing_number: '',
    account_number: '',
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [conns, accs] = await Promise.all([
        getBankConnections(),
        getAccounts(),
      ]);
      setConnections(conns);
      setAccounts(accs);
    } catch {
      setError('Failed to load bank connections');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo(
        sectionRef.current,
        { opacity: 0, y: 30 },
        {
          opacity: 1, y: 0, duration: 0.5, ease: 'power3.out',
          scrollTrigger: { trigger: sectionRef.current, start: 'top 80%', toggleActions: 'play none none none' },
        }
      );
    }, sectionRef);
    return () => ctx.revert();
  }, [loading, connections]);

  const handleCreate = async () => {
    if (!createForm.account_id || !createForm.institution_name || !createForm.ofx_username || !createForm.ofx_password) {
      toast({ title: 'Missing fields', description: 'Account, institution, username, and password are required.', variant: 'destructive' });
      return;
    }
    try {
      await createBankConnection({
        account_id: parseInt(createForm.account_id),
        institution_name: createForm.institution_name,
        connection_type: 'ofx',
        ofx_username: createForm.ofx_username,
        ofx_password: createForm.ofx_password,
        ofx_url: createForm.ofx_url || undefined,
        ofx_org: createForm.ofx_org || undefined,
        ofx_fid: createForm.ofx_fid || undefined,
        routing_number: createForm.routing_number || undefined,
        account_number: createForm.account_number || undefined,
      });
      toast({ title: 'Connection created', description: createForm.institution_name });
      setCreateOpen(false);
      setCreateForm({ account_id: '', institution_name: '', ofx_username: '', ofx_password: '', ofx_url: '', ofx_org: '', ofx_fid: '', routing_number: '', account_number: '' });
      fetchData();
    } catch (e: any) {
      toast({ title: 'Create failed', description: e.message, variant: 'destructive' });
    }
  };

  const handleFetch = async (connId: number) => {
    setFetching(connId);
    try {
      const result = await fetchBankTransactions(connId);
      toast({ title: 'Fetch completed', description: `${result.transactions_fetched} transactions fetched` });
      fetchData();
    } catch (e: any) {
      toast({ title: 'Fetch failed', description: e.message, variant: 'destructive' });
    } finally {
      setFetching(null);
    }
  };

  const handleDelete = async (connId: number, name: string) => {
    if (!confirm(`Delete connection to "${name}"?`)) return;
    try {
      await deleteBankConnection(connId);
      toast({ title: 'Connection deleted', description: name });
      fetchData();
    } catch (e: any) {
      toast({ title: 'Delete failed', description: e.message, variant: 'destructive' });
    }
  };

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
              <Building className="text-gold" size={28} />
              Bank Connections
            </h1>
            <p className="font-sans text-sm text-text-secondary mt-1">
              Manage OFX connections to financial institutions for automated transaction fetching.
            </p>
          </div>
          <Button onClick={() => setCreateOpen(true)} className="bg-gold text-black hover:bg-gold/90">
            <Plus size={16} className="mr-1" /> New Connection
          </Button>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20 mb-6">
            <AlertCircle size={16} />{error}
          </div>
        )}

        {loading ? (
          <div className="text-text-secondary text-sm">Loading connections...</div>
        ) : connections.length === 0 ? (
          <Card className="bg-surface border-divider">
            <CardContent className="p-8 text-center">
              <Building size={32} className="text-text-secondary mx-auto mb-3" />
              <p className="text-text-secondary font-sans text-sm mb-4">No bank connections configured.</p>
              <Button onClick={() => setCreateOpen(true)} className="bg-gold text-black hover:bg-gold/90">
                <Plus size={16} className="mr-1" /> Add First Connection
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {connections.map(conn => (
              <Card key={conn.id} className="bg-surface border-divider">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <CardTitle className="font-sans text-sm font-medium text-text-primary">{conn.institution_name}</CardTitle>
                    <Badge variant="outline" className={`text-xs ${conn.status === 'active' ? 'border-emerald-400/30 text-emerald-400' : 'border-text-secondary/30 text-text-secondary'}`}>
                      {conn.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 mb-4 text-xs">
                    <div className="flex justify-between text-text-secondary">
                      <span>Username</span>
                      <span className="font-mono text-text-primary">{conn.ofx_username}</span>
                    </div>
                    <div className="flex justify-between text-text-secondary">
                      <span>Password</span>
                      <span className="font-mono text-text-primary">{conn.ofx_password_masked}</span>
                    </div>
                    {conn.routing_number && (
                      <div className="flex justify-between text-text-secondary">
                        <span>Routing</span>
                        <span className="font-mono text-text-primary">{conn.routing_number}</span>
                      </div>
                    )}
                    {conn.account_number_masked && (
                      <div className="flex justify-between text-text-secondary">
                        <span>Account</span>
                        <span className="font-mono text-text-primary">{conn.account_number_masked}</span>
                      </div>
                    )}
                    <div className="flex justify-between text-text-secondary">
                      <span>Last Sync</span>
                      <span className="font-mono text-text-primary">{conn.last_sync ? new Date(conn.last_sync).toLocaleString() : 'Never'}</span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" className="flex-1 text-xs" onClick={() => handleFetch(conn.id)} disabled={fetching === conn.id}>
                      <Download size={12} className="mr-1" /> {fetching === conn.id ? 'Fetching...' : 'Fetch'}
                    </Button>
                    <Button size="sm" variant="outline" className="text-red-400 border-red-400/30 hover:bg-red-400/10" onClick={() => handleDelete(conn.id, conn.institution_name)}>
                      <Trash2 size={12} />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-surface border-divider text-text-primary max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-sans text-sm">New OFX Connection</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label className="font-sans text-xs text-text-secondary">Linked Account</Label>
              <Select value={createForm.account_id} onValueChange={v => setCreateForm(f => ({ ...f, account_id: v }))}>
                <SelectTrigger className="bg-canvas border-divider text-sm"><SelectValue placeholder="Select account" /></SelectTrigger>
                <SelectContent>
                  {accounts.map(a => <SelectItem key={a.id} value={String(a.id)}>{a.name} ({a.institution})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="font-sans text-xs text-text-secondary">Institution Name</Label>
              <Input value={createForm.institution_name} onChange={e => setCreateForm(f => ({ ...f, institution_name: e.target.value }))} placeholder="e.g. Chase Bank" className="bg-canvas border-divider text-sm" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="font-sans text-xs text-text-secondary">OFX Username</Label>
                <Input value={createForm.ofx_username} onChange={e => setCreateForm(f => ({ ...f, ofx_username: e.target.value }))} className="bg-canvas border-divider text-sm" />
              </div>
              <div>
                <Label className="font-sans text-xs text-text-secondary">OFX Password</Label>
                <Input type="password" value={createForm.ofx_password} onChange={e => setCreateForm(f => ({ ...f, ofx_password: e.target.value }))} className="bg-canvas border-divider text-sm" />
              </div>
            </div>
            <div>
              <Label className="font-sans text-xs text-text-secondary">OFX URL (optional)</Label>
              <Input value={createForm.ofx_url} onChange={e => setCreateForm(f => ({ ...f, ofx_url: e.target.value }))} placeholder="https://..." className="bg-canvas border-divider text-sm" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="font-sans text-xs text-text-secondary">OFX Org (optional)</Label>
                <Input value={createForm.ofx_org} onChange={e => setCreateForm(f => ({ ...f, ofx_org: e.target.value }))} className="bg-canvas border-divider text-sm" />
              </div>
              <div>
                <Label className="font-sans text-xs text-text-secondary">OFX FID (optional)</Label>
                <Input value={createForm.ofx_fid} onChange={e => setCreateForm(f => ({ ...f, ofx_fid: e.target.value }))} className="bg-canvas border-divider text-sm" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="font-sans text-xs text-text-secondary">Routing Number</Label>
                <Input value={createForm.routing_number} onChange={e => setCreateForm(f => ({ ...f, routing_number: e.target.value }))} className="bg-canvas border-divider text-sm" />
              </div>
              <div>
                <Label className="font-sans text-xs text-text-secondary">Account Number</Label>
                <Input value={createForm.account_number} onChange={e => setCreateForm(f => ({ ...f, account_number: e.target.value }))} className="bg-canvas border-divider text-sm" />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} className="bg-gold text-black hover:bg-gold/90">Create Connection</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
