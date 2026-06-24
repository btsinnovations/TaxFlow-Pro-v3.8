import { useState, useEffect, useRef } from 'react';
import { ChevronDown, ChevronUp, RotateCcw } from 'lucide-react';
import { getMLStatus, toggleML, runTests } from '@/hooks/useAPI';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';


gsap.registerPlugin(ScrollTrigger);

interface CategoryMetric {
  category: string;
  precision: number;
  recall: number;
}

interface ModelVersion {
  version: string;
  accuracy: number;
  status: 'Production' | 'Rolled Back' | 'Deprecated';
  date: string;
}

interface MLStatus {
  enabled: boolean;
  model_version?: string;
  accuracy?: number;
  last_trained?: string;
  training_samples?: number;
  message?: string;
  category_metrics?: CategoryMetric[];
  model_versions?: ModelVersion[];
}

function ToggleSwitch({ enabled, onChange }: { enabled: boolean; onChange?: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange?.(!enabled)}
      className="w-9 h-5 rounded-full relative transition-colors duration-200"
      style={{ backgroundColor: enabled ? '#4ADE80' : '#3A3A3A' }}
    >
      <div
        className="w-3.5 h-3.5 rounded-full bg-white absolute top-0.5 transition-all duration-200"
        style={{ left: enabled ? '18px' : '2px' }}
      />
    </button>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-surface border border-divider rounded-lg p-5 animate-pulse">
      <div className="h-2 bg-canvas rounded w-1/2 mb-3" />
      <div className="h-6 bg-canvas rounded w-1/3" />
    </div>
  );
}

function SkeletonBar() {
  return (
    <div className="space-y-2 animate-pulse">
      <div className="h-2 bg-canvas rounded w-full" />
      <div className="h-2 bg-canvas rounded w-5/6" />
    </div>
  );
}

export default function MLTraining() {
  const [status, setStatus] = useState<MLStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const sectionRef = useRef<HTMLDivElement>(null);

  const loadStatus = async () => {
    try {
      setLoading(true);
      const data = await getMLStatus();
      setStatus(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load ML status');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    const ctx = gsap.context(() => {
      gsap.fromTo(sectionRef.current, { opacity: 0, y: 30 }, {
        opacity: 1, y: 0, duration: 0.5, ease: 'power3.out',
        scrollTrigger: { trigger: sectionRef.current, start: 'top 80%', toggleActions: 'play none none none' },
      });
    });
    return () => ctx.revert();
  }, []);

  const handleToggle = async (_value: boolean) => {
    try {
      setActionLoading(true);
      await toggleML();
      await loadStatus();
    } catch (err: any) {
      setError(err.message || 'Failed to toggle ML');
    } finally {
      setActionLoading(false);
    }
  };

  const handleTrain = async () => {
    try {
      setActionLoading(true);
      await runTests();
      await loadStatus();
    } catch (err: any) {
      setError(err.message || 'Failed to trigger training');
    } finally {
      setActionLoading(false);
    }
  };

  const statusConfig = {
    Production: { bg: 'rgba(74, 222, 128, 0.15)', text: '#4ADE80' },
    'Rolled Back': { bg: 'rgba(251, 191, 36, 0.15)', text: '#FBBF24' },
    Deprecated: { bg: 'rgba(248, 113, 113, 0.15)', text: '#F87171' },
  };

  const metrics = status?.category_metrics || [];
  const versions = status?.model_versions || [];

  const overallAccuracy = status?.accuracy != null ? `${(status.accuracy * 100).toFixed(1)}%` : '—';
  const precision = metrics.length
    ? `${(metrics.reduce((a, m) => a + m.precision, 0) / metrics.length).toFixed(1)}%`
    : '—';
  const recall = metrics.length
    ? `${(metrics.reduce((a, m) => a + m.recall, 0) / metrics.length).toFixed(1)}%`
    : '—';

  return (
    <section id="ml-training" className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h2 className="font-serif text-[32px] text-text-primary">ML Model Management</h2>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Monitor categorization accuracy, trigger incremental training, and manage model versions.
          </p>
        </div>

        {error && (
          <div className="mb-4 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Panel - Model Metrics */}
          <div className="space-y-4">
            {/* Metric Cards */}
            <div className="grid grid-cols-3 gap-4">
              {loading ? (
                <>
                  <SkeletonCard />
                  <SkeletonCard />
                  <SkeletonCard />
                </>
              ) : (
                [
                  { label: 'Overall Accuracy', value: overallAccuracy, color: '#4ADE80' },
                  { label: 'Precision', value: precision, color: '#60A5FA' },
                  { label: 'Recall', value: recall, color: '#C9A96E' },
                ].map(metric => (
                  <div key={metric.label} className="bg-surface border border-divider rounded-lg p-5">
                    <div className="font-mono text-[10px] uppercase text-text-secondary mb-2">{metric.label}</div>
                    <div className="font-mono text-[28px]" style={{ color: metric.color }}>{metric.value}</div>
                  </div>
                ))
              )}
            </div>

            {/* Category Breakdown */}
            <div className="bg-surface border border-divider rounded-lg p-6">
              <h3 className="font-sans text-sm font-medium text-text-primary mb-4">Category Breakdown</h3>
              {loading ? (
                <div className="space-y-3">
                  <SkeletonBar />
                  <SkeletonBar />
                  <SkeletonBar />
                </div>
              ) : metrics.length === 0 ? (
                <p className="font-sans text-sm text-text-secondary">No category metrics available.</p>
              ) : (
                <div className="space-y-3">
                  {metrics.map(cat => (
                    <div key={cat.category}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-sans text-sm text-text-primary">{cat.category}</span>
                        <div className="flex gap-4">
                          <span className="font-mono text-xs text-info">{cat.precision}%</span>
                          <span className="font-mono text-xs text-gold">{cat.recall}%</span>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <div className="flex-1 h-1.5 bg-canvas rounded-full overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${Math.min(cat.precision, 100)}%`, backgroundColor: 'rgba(96, 165, 250, 0.4)' }} />
                        </div>
                        <div className="flex-1 h-1.5 bg-canvas rounded-full overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${Math.min(cat.recall, 100)}%`, backgroundColor: 'rgba(201, 169, 110, 0.4)' }} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Panel - Training Controls */}
          <div className="space-y-4">
            {/* Current Model Card */}
            <div className="bg-surface border border-divider rounded-lg p-6">
              {loading ? (
                <SkeletonBar />
              ) : (
                <>
                  <div className="font-mono text-sm text-gold mb-1">{status?.model_version || 'No model'}</div>
                  <div className="font-sans text-xs text-text-secondary">
                    {status?.message || 'ML status unavailable'}
                  </div>
                </>
              )}
            </div>

            {/* Training Dataset */}
            <div className="bg-surface border border-divider rounded-lg p-6">
              {loading ? (
                <SkeletonBar />
              ) : (
                <>
                  <div className="font-mono text-[10px] uppercase text-text-secondary mb-2">Training Dataset</div>
                  <div className="font-sans text-sm text-text-primary">
                    {status?.training_samples != null ? `${status.training_samples.toLocaleString()} labeled transactions` : 'No training data'}
                  </div>
                </>
              )}
            </div>

            {/* Incremental Training */}
            <div className="bg-surface border border-divider rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="font-sans text-sm font-medium text-text-primary">Incremental Training</div>
                  <div className="font-sans text-xs text-text-secondary mt-1">
                    Automatically retrain model on new verified transactions.
                  </div>
                </div>
                <ToggleSwitch enabled={!!status?.enabled} onChange={handleToggle} />
              </div>

              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="font-mono text-[10px] uppercase text-text-secondary">Status</span>
                  <span className="font-mono text-sm text-text-primary">{status?.enabled ? 'Enabled' : 'Disabled'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-mono text-[10px] uppercase text-text-secondary">Estimated Training Time</span>
                  <span className="font-mono text-sm text-text-secondary">{status?.enabled ? '4 minutes' : '—'}</span>
                </div>
              </div>

              <button
                onClick={handleTrain}
                disabled={actionLoading || loading}
                className="w-full mt-4 bg-gold text-canvas font-sans text-sm font-medium py-3.5 rounded-md transition-all duration-200 hover:bg-gold-hover disabled:opacity-50"
              >
                {actionLoading ? 'Running...' : 'Train Now'}
              </button>
            </div>

            {/* Model Versions */}
            <div className="bg-surface border border-divider rounded-lg p-6">
              <button
                onClick={() => setVersionsOpen(!versionsOpen)}
                className="flex items-center justify-between w-full"
              >
                <span className="font-sans text-sm font-medium text-text-primary">Model Versions</span>
                {versionsOpen ? <ChevronUp size={16} className="text-text-secondary" /> : <ChevronDown size={16} className="text-text-secondary" />}
              </button>

              {versionsOpen && (
                <div className="mt-4 space-y-3">
                  {loading ? (
                    <SkeletonBar />
                  ) : versions.length === 0 ? (
                    <p className="font-sans text-xs text-text-secondary">No model versions available.</p>
                  ) : (
                    versions.map(ver => (
                      <div key={ver.version} className="flex items-center justify-between py-2 border-t border-divider">
                        <div className="flex items-center gap-3">
                          <span className="font-mono text-sm text-gold">{ver.version}</span>
                          <span className="font-mono text-xs text-text-secondary">{ver.accuracy}%</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span
                            className="font-mono text-[10px] px-2 py-0.5 rounded"
                            style={{ backgroundColor: statusConfig[ver.status]?.bg, color: statusConfig[ver.status]?.text }}
                          >
                            {ver.status}
                          </span>
                          {ver.status !== 'Production' && (
                            <button className="flex items-center gap-1 text-xs text-gold hover:text-gold-hover transition-colors">
                              <RotateCcw size={12} />
                              Rollback
                            </button>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
