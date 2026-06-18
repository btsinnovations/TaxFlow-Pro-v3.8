import { useEffect, useState, useRef, useCallback } from 'react';
import { Package, Upload, AlertCircle, RefreshCw, Clock, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { createBatchImport, listBatchJobs } from '@/hooks/useAPI';
import { useClient } from '@/context/ClientContext';
import { useToast } from '@/hooks/useToast';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface BatchJob {
  job_id: number;
  filename: string;
  status: string;
  total_rows: number;
  processed_rows: number;
  error_rows: number;
  error_log: string | null;
  completed_at: string | null;
  created_at: string;
}

const STATUS_CONFIG: Record<string, { icon: any; color: string; label: string }> = {
  pending: { icon: Clock, color: 'text-amber-400', label: 'Pending' },
  completed: { icon: CheckCircle, color: 'text-emerald-400', label: 'Completed' },
  completed_with_errors: { icon: AlertTriangle, color: 'text-amber-400', label: 'Completed with Errors' },
  failed: { icon: XCircle, color: 'text-red-400', label: 'Failed' },
  processing: { icon: RefreshCw, color: 'text-blue-400', label: 'Processing' },
};

export default function BatchImportPage() {
  const { selectedClient } = useClient();
  const { toast } = useToast();
  const sectionRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [jobs, setJobs] = useState<BatchJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const fetchData = useCallback(async () => {
    if (!selectedClient) { setLoading(false); return; }
    setLoading(true);
    try {
      const data = await listBatchJobs(selectedClient.id);
      setJobs(data.jobs || []);
    } catch {
      setError('Failed to load batch jobs');
    } finally {
      setLoading(false);
    }
  }, [selectedClient]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Poll for pending/processing jobs
  useEffect(() => {
    const hasActive = jobs.some(j => j.status === 'pending' || j.status === 'processing');
    if (!hasActive) return;
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [jobs, fetchData]);

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
  }, [loading, jobs]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setSelectedFile(file);
  };

  const handleUpload = async () => {
    if (!selectedClient || !selectedFile) return;
    setUploading(true);
    setError('');
    try {
      const result = await createBatchImport(selectedClient.id, selectedFile);
      toast({ title: 'Import started', description: `Job #${result.job_id} created` });
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      fetchData();
    } catch (e: any) {
      setError(e.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
            <Package className="text-gold" size={28} />
            Batch Import
          </h1>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Upload ZIP archives of CSV transaction files and monitor background import jobs.
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20 mb-6">
            <AlertCircle size={16} />{error}
          </div>
        )}

        {/* Upload Area */}
        <Card className="bg-surface border-divider mb-6">
          <CardHeader>
            <CardTitle className="font-sans text-sm font-medium text-text-primary flex items-center gap-2">
              <Upload size={16} className="text-gold" />
              Upload ZIP Archive
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip"
                onChange={handleFileSelect}
                className="text-xs text-text-secondary"
              />
              <Button
                className="bg-gold text-black hover:bg-gold/90"
                onClick={handleUpload}
                disabled={uploading || !selectedFile}
              >
                {uploading ? 'Uploading...' : 'Start Import'}
              </Button>
              {selectedFile && (
                <span className="font-mono text-xs text-text-secondary">{selectedFile.name}</span>
              )}
            </div>
            <p className="font-sans text-[11px] text-text-secondary mt-2">
              ZIP must contain CSV files with columns: date, description, amount (required), plus optional: category, tx_type.
            </p>
          </CardContent>
        </Card>

        {/* Jobs List */}
        {!selectedClient ? (
          <div className="bg-surface border border-divider rounded-lg p-8 text-center">
            <p className="text-text-secondary font-sans text-sm mb-4">Select a client.</p>
          </div>
        ) : loading ? (
          <div className="text-text-secondary text-sm">Loading jobs...</div>
        ) : jobs.length === 0 ? (
          <Card className="bg-surface border-divider">
            <CardContent className="p-8 text-center">
              <Package size={32} className="text-text-secondary mx-auto mb-3" />
              <p className="text-text-secondary font-sans text-sm">No import jobs yet.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {jobs.map(job => {
              const config = STATUS_CONFIG[job.status] || STATUS_CONFIG.pending;
              const StatusIcon = config.icon;
              const pct = job.total_rows > 0 ? (job.processed_rows / job.total_rows) * 100 : 0;
              return (
                <Card key={job.job_id} className="bg-surface border-divider">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono text-sm text-gold">#{job.job_id}</span>
                          <span className="font-sans text-sm text-text-primary">{job.filename}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <StatusIcon size={14} className={config.color} />
                          <span className={`font-sans text-xs ${config.color}`}>{config.label}</span>
                          <span className="font-mono text-[11px] text-text-secondary">
                            Created: {new Date(job.created_at).toLocaleString()}
                          </span>
                          {job.completed_at && (
                            <span className="font-mono text-[11px] text-text-secondary">
                              Completed: {new Date(job.completed_at).toLocaleString()}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-4 mb-3 text-xs">
                      <div>
                        <span className="text-text-secondary">Total Rows</span>
                        <span className="font-mono text-text-primary ml-2">{job.total_rows.toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-text-secondary">Processed</span>
                        <span className="font-mono text-emerald-400 ml-2">{job.processed_rows.toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-text-secondary">Errors</span>
                        <span className={`font-mono ml-2 ${job.error_rows > 0 ? 'text-red-400' : 'text-text-primary'}`}>
                          {job.error_rows.toLocaleString()}
                        </span>
                      </div>
                    </div>
                    {(job.status === 'pending' || job.status === 'processing') && (
                      <div className="mb-2">
                        <div className="w-full h-1.5 bg-canvas rounded-full overflow-hidden">
                          <div className="h-full bg-blue-400 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    )}
                    {job.error_log && (
                      <details className="text-xs">
                        <summary className="cursor-pointer text-text-secondary hover:text-text-primary">View Error Log</summary>
                        <pre className="bg-canvas rounded p-3 mt-2 text-[11px] text-red-400 overflow-x-auto whitespace-pre-wrap font-mono">
                          {job.error_log}
                        </pre>
                      </details>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
