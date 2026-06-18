import { useEffect, useState, useRef, useCallback } from 'react';
import { FileSignature, AlertCircle, Shield, FileText, Eye, Clock } from 'lucide-react';
import { getSignedReports, getSignedReport } from '@/hooks/useAPI';
import { useClient } from '@/context/ClientContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface SignedReport {
  id: number;
  tenant_id: number;
  user_id: number;
  report_type: string;
  period_start: string | null;
  period_end: string | null;
  file_path: string;
  signature_hash: string;
  signed_at: string;
}

const REPORT_TYPE_LABELS: Record<string, string> = {
  pl: 'Profit & Loss',
  balance_sheet: 'Balance Sheet',
  cash_flow: 'Cash Flow',
  tax_summary: 'Tax Summary',
  general_ledger: 'General Ledger',
  trial_balance: 'Trial Balance',
};

export default function ReportsPage() {
  const { selectedClient } = useClient();
  const sectionRef = useRef<HTMLDivElement>(null);

  const [reports, setReports] = useState<SignedReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Detail dialog
  const [selectedReport, setSelectedReport] = useState<SignedReport | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!selectedClient) return;
    setLoading(true);
    setError('');
    try {
      const data = await getSignedReports(selectedClient.id);
      setReports(data);
    } catch {
      setError('Failed to load signed reports');
    } finally {
      setLoading(false);
    }
  }, [selectedClient]);

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
  }, [loading, reports]);

  const loadDetail = async (report: SignedReport) => {
    setDetailLoading(true);
    setSelectedReport(report);
    try {
      const data = await getSignedReport(report.id);
      setSelectedReport(data);
    } catch (e: any) {
      setError('Failed to load report details');
    } finally {
      setDetailLoading(false);
    }
  };

  const formatDate = (d: string) => {
    try { return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }); }
    catch { return d; }
  };

  const formatDateTime = (d: string) => {
    try { return new Date(d).toLocaleString('en-US'); }
    catch { return d; }
  };

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
            <FileSignature className="text-gold" size={28} />
            Signed Reports
          </h1>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Tamper-evident reports with HMAC-SHA256 cryptographic signatures.
          </p>
        </div>

        {loading ? (
          <div className="text-text-secondary font-sans text-sm">Loading signed reports...</div>
        ) : error ? (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20">
            <AlertCircle size={16} />{error}
          </div>
        ) : reports.length === 0 ? (
          <Card className="bg-surface border-divider">
            <CardContent className="p-8 text-center">
              <FileText size={32} className="text-text-secondary mx-auto mb-3" />
              <p className="text-text-secondary font-sans text-sm mb-1">No signed reports yet.</p>
              <p className="text-text-secondary font-sans text-xs">Signed reports are generated when you sign financial documents for audit compliance.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {reports.map(r => (
              <Card key={r.id} className="bg-surface border-divider">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <CardTitle className="font-sans text-sm font-medium text-text-primary">
                      {REPORT_TYPE_LABELS[r.report_type] || r.report_type}
                    </CardTitle>
                    <Badge variant="outline" className="text-xs border-emerald-400/30 text-emerald-400">
                      <Shield size={10} className="mr-1" /> Signed
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 mb-4">
                    {r.file_path && (
                      <div className="font-sans text-xs text-text-secondary">
                        <span className="text-text-secondary">Title:</span> {r.file_path}
                      </div>
                    )}
                    {r.period_start && r.period_end && (
                      <div className="font-sans text-xs text-text-secondary">
                        Period: {r.period_start} → {r.period_end}
                      </div>
                    )}
                    <div className="flex items-center gap-1.5 font-sans text-xs text-text-secondary">
                      <Clock size={12} />
                      Signed: {formatDateTime(r.signed_at)}
                    </div>
                    <div className="font-mono text-[10px] text-text-secondary truncate">
                      SHA256: {r.signature_hash.slice(0, 16)}...
                    </div>
                  </div>
                  <Button size="sm" variant="outline" className="w-full text-xs" onClick={() => loadDetail(r)}>
                    <Eye size={12} className="mr-1" /> View Details
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Detail Dialog */}
      <Dialog open={!!selectedReport} onOpenChange={(open) => { if (!open) setSelectedReport(null); }}>
        <DialogContent className="bg-surface border-divider text-text-primary max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-sans text-sm flex items-center gap-2">
              <Shield size={16} className="text-emerald-400" />
              Report Details
            </DialogTitle>
          </DialogHeader>
          {detailLoading ? (
            <div className="py-8 text-center text-text-secondary text-sm">Loading report details...</div>
          ) : selectedReport ? (
            <div className="space-y-4 py-2">
              <div className="bg-canvas rounded-lg p-4 space-y-3">
                <div>
                  <div className="font-sans text-[10px] uppercase tracking-wide text-text-secondary">Report Type</div>
                  <div className="font-sans text-sm text-text-primary">{REPORT_TYPE_LABELS[selectedReport.report_type] || selectedReport.report_type}</div>
                </div>
                {selectedReport.file_path && (
                  <div>
                    <div className="font-sans text-[10px] uppercase tracking-wide text-text-secondary">Title</div>
                    <div className="font-sans text-sm text-text-primary">{selectedReport.file_path}</div>
                  </div>
                )}
                {selectedReport.period_start && (
                  <div>
                    <div className="font-sans text-[10px] uppercase tracking-wide text-text-secondary">Period</div>
                    <div className="font-mono text-sm text-text-primary">{selectedReport.period_start} → {selectedReport.period_end || 'Present'}</div>
                  </div>
                )}
                <div>
                  <div className="font-sans text-[10px] uppercase tracking-wide text-text-secondary">Signed At</div>
                  <div className="font-mono text-sm text-text-primary">{formatDateTime(selectedReport.signed_at)}</div>
                </div>
                <div>
                  <div className="font-sans text-[10px] uppercase tracking-wide text-text-secondary">HMAC-SHA256 Signature</div>
                  <div className="font-mono text-xs text-gold break-all mt-1 bg-surface p-2 rounded">{selectedReport.signature_hash}</div>
                </div>
                <div>
                  <div className="font-sans text-[10px] uppercase tracking-wide text-text-secondary">Report ID</div>
                  <div className="font-mono text-xs text-text-secondary">#{selectedReport.id}</div>
                </div>
              </div>
              <div className="flex items-start gap-2 p-3 bg-emerald-400/10 border border-emerald-400/20 rounded-lg">
                <Shield size={14} className="text-emerald-400 mt-0.5 shrink-0" />
                <div>
                  <div className="font-sans text-xs text-emerald-400 font-medium">Tamper-Evident</div>
                  <div className="font-sans text-[11px] text-text-secondary mt-0.5">
                    This report has been cryptographically signed. Any modification to the data will invalidate the signature hash.
                  </div>
                </div>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button onClick={() => setSelectedReport(null)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
