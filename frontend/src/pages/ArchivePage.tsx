import { useEffect, useState, useRef } from 'react';
import { Archive, RotateCcw, AlertCircle, Shield } from 'lucide-react';
import { archiveYear, restoreYear } from '@/hooks/useAPI';
import { useClient } from '@/context/ClientContext';
import { useToast } from '@/hooks/useToast';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const CURRENT_YEAR = new Date().getFullYear();

export default function ArchivePage() {
  const { selectedClient } = useClient();
  const { toast } = useToast();
  const sectionRef = useRef<HTMLDivElement>(null);

  const [archiveYearVal, setArchiveYearVal] = useState(CURRENT_YEAR - 1);
  const [restoreYearVal, setRestoreYearVal] = useState(CURRENT_YEAR - 1);
  const [restoring, setRestoring] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [error, setError] = useState('');
  const [lastAction, setLastAction] = useState<{ type: string; result: any } | null>(null);

  // Restore dialog
  const [restoreOpen, setRestoreOpen] = useState(false);
  const [masterPassword, setMasterPassword] = useState('');

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
  }, []);

  const handleArchive = async () => {
    if (!selectedClient) { setError('Please select a client'); return; }
    setArchiving(true);
    setError('');
    try {
      const result = await archiveYear(selectedClient.id, archiveYearVal);
      setLastAction({ type: 'archive', result });
      toast({ title: 'Archived', description: result.message });
    } catch (e: any) {
      setError(e.message || 'Failed to archive year');
    } finally {
      setArchiving(false);
    }
  };

  const handleRestore = async () => {
    if (!selectedClient || !masterPassword) return;
    setRestoring(true);
    setError('');
    try {
      const result = await restoreYear(selectedClient.id, restoreYearVal, masterPassword);
      setLastAction({ type: 'restore', result });
      toast({ title: 'Restored', description: result.message });
      setRestoreOpen(false);
      setMasterPassword('');
    } catch (e: any) {
      setError(e.message || 'Failed to restore year');
    } finally {
      setRestoring(false);
    }
  };

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
            <Archive className="text-gold" size={28} />
            Archive & Restore
          </h1>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Archive a client's transactions by tax year and restore them when needed.
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20 mb-6">
            <AlertCircle size={16} />{error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Archive Card */}
          <Card className="bg-surface border-divider">
            <CardHeader>
              <CardTitle className="font-sans text-sm font-medium text-text-primary flex items-center gap-2">
                <Archive size={16} className="text-gold" />
                Archive Transactions
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="font-sans text-xs text-text-secondary">
                Move all transactions for a given tax year into a secure archive file.
                Archived transactions are hidden from the active transaction list.
              </p>
              <div>
                <Label className="font-sans text-xs text-text-secondary">Tax Year</Label>
                <select
                  value={archiveYearVal}
                  onChange={e => setArchiveYearVal(Number(e.target.value))}
                  className="w-full bg-canvas border border-divider rounded-lg px-3 py-2 text-sm text-text-primary font-mono"
                >
                  {Array.from({ length: 10 }, (_, i) => CURRENT_YEAR - 1 - i).map(y => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
              </div>
              <Button
                className="w-full bg-gold text-black hover:bg-gold/90"
                onClick={handleArchive}
                disabled={archiving || !selectedClient}
              >
                {archiving ? 'Archiving...' : 'Archive Year'}
              </Button>
            </CardContent>
          </Card>

          {/* Restore Card */}
          <Card className="bg-surface border-divider">
            <CardHeader>
              <CardTitle className="font-sans text-sm font-medium text-text-primary flex items-center gap-2">
                <RotateCcw size={16} className="text-blue-400" />
                Restore Transactions
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="font-sans text-xs text-text-secondary">
                Restore previously archived transactions back to the active database.
                Requires the archive master password for verification.
              </p>
              <div>
                <Label className="font-sans text-xs text-text-secondary">Tax Year</Label>
                <select
                  value={restoreYearVal}
                  onChange={e => setRestoreYearVal(Number(e.target.value))}
                  className="w-full bg-canvas border border-divider rounded-lg px-3 py-2 text-sm text-text-primary font-mono"
                >
                  {Array.from({ length: 10 }, (_, i) => CURRENT_YEAR - 1 - i).map(y => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
              </div>
              <Button
                className="w-full border border-blue-400/30 text-blue-400 hover:bg-blue-400/10 bg-transparent"
                onClick={() => setRestoreOpen(true)}
                disabled={!selectedClient}
              >
                <RotateCcw size={14} className="mr-1" /> Restore Year
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Last Action Result */}
        {lastAction && (
          <Card className="bg-surface border-divider mt-6">
            <CardHeader>
              <CardTitle className="font-sans text-sm font-medium text-text-primary">
                Last Action: {lastAction.type === 'archive' ? 'Archived' : 'Restored'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-canvas rounded-lg p-4">
                <p className="font-sans text-sm text-text-primary">{lastAction.result.message}</p>
                <p className="font-mono text-xs text-text-secondary mt-2">
                  {lastAction.result.count} transaction(s) • Year: {lastAction.type === 'archive' ? archiveYearVal : restoreYearVal}
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Restore Password Dialog */}
      <Dialog open={restoreOpen} onOpenChange={setRestoreOpen}>
        <DialogContent className="bg-surface border-divider text-text-primary">
          <DialogHeader>
            <DialogTitle className="font-sans text-sm flex items-center gap-2">
              <Shield size={16} className="text-amber-400" />
              Enter Master Password
            </DialogTitle>
          </DialogHeader>
          <div className="py-4 space-y-3">
            <p className="font-sans text-xs text-text-secondary">
              Restoring year {restoreYearVal} for {selectedClient?.name}. This requires the archive master password.
            </p>
            <div>
              <Label className="font-sans text-xs text-text-secondary">Master Password</Label>
              <Input
                type="password"
                value={masterPassword}
                onChange={e => setMasterPassword(e.target.value)}
                placeholder="Enter master password"
                className="bg-canvas border-divider text-sm"
                onKeyDown={e => e.key === 'Enter' && handleRestore()}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => { setRestoreOpen(false); setMasterPassword(''); }}>Cancel</Button>
            <Button onClick={handleRestore} disabled={restoring || !masterPassword}>
              {restoring ? 'Restoring...' : 'Restore'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
