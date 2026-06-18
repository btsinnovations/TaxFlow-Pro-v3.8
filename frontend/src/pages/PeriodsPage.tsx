import { useEffect, useState, useRef, useCallback } from 'react';
import { CalendarClock, Plus, Lock, Unlock, AlertCircle, AlertTriangle, CheckCircle } from 'lucide-react';
import { getPeriods, createPeriod, lockPeriod, unlockPeriod } from '@/hooks/useAPI';
import { useClient } from '@/context/ClientContext';
import { useToast } from '@/hooks/useToast';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface Period {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  status: string;
  is_locked: boolean;
}

const CURRENT_YEAR = new Date().getFullYear();

export default function PeriodsPage() {
  const { selectedClient } = useClient();
  const { toast } = useToast();
  const sectionRef = useRef<HTMLDivElement>(null);

  const [periods, setPeriods] = useState<Period[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [year, setYear] = useState(String(CURRENT_YEAR));

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: '',
    start_date: '',
    end_date: '',
    status: 'open',
  });

  // Lock confirmation
  const [lockConfirm, setLockConfirm] = useState<Period | null>(null);
  const [lockWarning, setLockWarning] = useState('');

  const fetchData = useCallback(async () => {
    if (!selectedClient) { setLoading(false); return; }
    setLoading(true);
    try {
      const data = await getPeriods(selectedClient.id, year);
      setPeriods(data);
    } catch {
      setError('Failed to load periods');
    } finally {
      setLoading(false);
    }
  }, [selectedClient, year]);

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
  }, [loading, periods]);

  const handleCreate = async () => {
    if (!selectedClient || !createForm.name || !createForm.start_date || !createForm.end_date) {
      toast({ title: 'Missing fields', description: 'Name, start date, and end date are required.', variant: 'destructive' });
      return;
    }
    try {
      await createPeriod(selectedClient.id, {
        name: createForm.name,
        start_date: createForm.start_date,
        end_date: createForm.end_date,
        status: createForm.status,
      });
      toast({ title: 'Period created', description: createForm.name });
      setCreateOpen(false);
      setCreateForm({ name: '', start_date: '', end_date: '', status: 'open' });
      fetchData();
    } catch (e: any) {
      toast({ title: 'Create failed', description: e.message, variant: 'destructive' });
    }
  };

  const handleLock = async (period: Period) => {
    try {
      const result = await lockPeriod(period.id);
      setLockWarning(result.warning || '');
      setLockConfirm(null);
      toast({
        title: 'Period locked',
        description: result.warning || `${period.name} is now locked.`,
      });
      fetchData();
    } catch (e: any) {
      toast({ title: 'Lock failed', description: e.message, variant: 'destructive' });
    }
  };

  const handleUnlock = async (period: Period) => {
    try {
      await unlockPeriod(period.id);
      toast({ title: 'Period unlocked', description: period.name });
      fetchData();
    } catch (e: any) {
      toast({ title: 'Unlock failed', description: e.message, variant: 'destructive' });
    }
  };

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
          <div>
            <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
              <CalendarClock className="text-gold" size={28} />
              Accounting Periods
            </h1>
            <p className="font-sans text-sm text-text-secondary mt-1">
              Define, lock, and manage accounting periods for each client.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={year}
              onChange={e => setYear(e.target.value)}
              className="bg-surface border border-divider rounded-lg px-3 py-2 text-sm text-text-primary font-mono"
            >
              {Array.from({ length: 5 }, (_, i) => CURRENT_YEAR - 2 + i).map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <Button onClick={() => setCreateOpen(true)} className="bg-gold text-black hover:bg-gold/90">
              <Plus size={16} className="mr-1" /> New Period
            </Button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20 mb-6">
            <AlertCircle size={16} />{error}
          </div>
        )}

        {loading ? (
          <div className="text-text-secondary text-sm">Loading periods...</div>
        ) : periods.length === 0 ? (
          <Card className="bg-surface border-divider">
            <CardContent className="p-8 text-center">
              <CalendarClock size={32} className="text-text-secondary mx-auto mb-3" />
              <p className="text-text-secondary font-sans text-sm mb-4">No accounting periods for {year}.</p>
              <Button onClick={() => setCreateOpen(true)} className="bg-gold text-black hover:bg-gold/90">
                <Plus size={16} className="mr-1" /> Create First Period
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {periods.map(p => (
              <Card key={p.id} className="bg-surface border-divider">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-sans text-sm font-medium text-text-primary">{p.name}</span>
                        <Badge variant="outline" className={`text-xs ${p.is_locked ? 'border-red-400/30 text-red-400' : 'border-emerald-400/30 text-emerald-400'}`}>
                          {p.is_locked ? 'Locked' : 'Open'}
                        </Badge>
                        <Badge variant="outline" className="text-xs border-text-secondary/30 text-text-secondary">{p.status}</Badge>
                      </div>
                      <div className="font-mono text-xs text-text-secondary">
                        {p.start_date} → {p.end_date}
                      </div>
                    </div>
                    <div className="flex gap-2 ml-4">
                      {!p.is_locked ? (
                        <Button size="sm" variant="outline" className="text-xs border-red-400/30 text-red-400 hover:bg-red-400/10" onClick={() => setLockConfirm(p)}>
                          <Lock size={12} className="mr-1" /> Lock
                        </Button>
                      ) : (
                        <Button size="sm" variant="outline" className="text-xs border-emerald-400/30 text-emerald-400 hover:bg-emerald-400/10" onClick={() => handleUnlock(p)}>
                          <Unlock size={12} className="mr-1" /> Unlock
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Create Period Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-surface border-divider text-text-primary">
          <DialogHeader>
            <DialogTitle className="font-sans text-sm">Create Accounting Period</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label className="font-sans text-xs text-text-secondary">Period Name</Label>
              <Input value={createForm.name} onChange={e => setCreateForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Q1 2026" className="bg-canvas border-divider text-sm" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="font-sans text-xs text-text-secondary">Start Date</Label>
                <Input type="date" value={createForm.start_date} onChange={e => setCreateForm(f => ({ ...f, start_date: e.target.value }))} className="bg-canvas border-divider text-sm" />
              </div>
              <div>
                <Label className="font-sans text-xs text-text-secondary">End Date</Label>
                <Input type="date" value={createForm.end_date} onChange={e => setCreateForm(f => ({ ...f, end_date: e.target.value }))} className="bg-canvas border-divider text-sm" />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} className="bg-gold text-black hover:bg-gold/90">Create Period</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Lock Confirmation Dialog */}
      <Dialog open={!!lockConfirm} onOpenChange={(open) => { if (!open) setLockConfirm(null); }}>
        <DialogContent className="bg-surface border-divider text-text-primary">
          <DialogHeader>
            <DialogTitle className="font-sans text-sm flex items-center gap-2">
              <AlertTriangle size={16} className="text-amber-400" />
              Lock Period: {lockConfirm?.name}
            </DialogTitle>
          </DialogHeader>
          <div className="py-4 space-y-3">
            <p className="font-sans text-sm text-text-secondary">
              Locking this period will prevent new journal entries from being posted within its date range.
            </p>
            <div className="bg-canvas rounded-lg p-3">
              <span className="font-mono text-xs text-text-secondary">{lockConfirm?.start_date} → {lockConfirm?.end_date}</span>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setLockConfirm(null)}>Cancel</Button>
            <Button onClick={() => lockConfirm && handleLock(lockConfirm)} className="bg-red-400/20 text-red-400 hover:bg-red-400/30 border border-red-400/30">
              <Lock size={14} className="mr-1" /> Lock Period
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Lock Warning Dialog */}
      <Dialog open={!!lockWarning} onOpenChange={(open) => { if (!open) setLockWarning(''); }}>
        <DialogContent className="bg-surface border-divider text-text-primary">
          <DialogHeader>
            <DialogTitle className="font-sans text-sm flex items-center gap-2">
              <CheckCircle size={16} className="text-emerald-400" />
              Period Locked
            </DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <div className="flex items-start gap-2 p-3 bg-amber-400/10 border border-amber-400/20 rounded-lg">
              <AlertTriangle size={14} className="text-amber-400 mt-0.5 shrink-0" />
              <p className="font-sans text-sm text-amber-400">{lockWarning}</p>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setLockWarning('')}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
