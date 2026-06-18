import { useState, useEffect, useRef } from 'react';
import { ChevronDown, ChevronUp, RotateCcw, Loader2, AlertCircle, Play } from 'lucide-react';
import { getMLStatus, toggleML, categorizeStatement } from '@/hooks/useAPI';
import { useToast } from '@/hooks/useToast';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

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

interface CategoryMetric {
  category: string;
  precision: number;
  recall: number;
}

export default function MLTraining() {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [categorizing, setCategorizing] = useState(false);
  const [statementId, setStatementId] = useState('');
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [error, setError] = useState('');
  const sectionRef = useRef<HTMLDivElement>(null);
  const { addToast } = useToast();

  const loadStatus = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getMLStatus();
      setStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load ML status');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo(sectionRef.current, { opacity: 0, y: 30 }, {
        opacity: 1, y: 0, duration: 0.5, ease: 'power3.out',
        scrollTrigger: { trigger: sectionRef.current, start: 'top 80%', toggleActions: 'play none none none' },
      });
    });
    return () => ctx.revert();
  }, [loading, status]);

  const handleToggle = async () => {
    setToggling(true);
    try {
      const result = await toggleML();
      addToast(result.message || 'ML toggle processed', 'info');
      await loadStatus();
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Failed to toggle ML', 'error');
    } finally {
      setToggling(false);
    }
  };

  const handleCategorize = async () => {
    if (!statementId || isNaN(Number(statementId))) {
      addToast('Please enter a valid statement ID', 'warning');
      return;
    }
    setCategorizing(true);
    try {
      const result = await categorizeStatement(statementId);
      addToast(
        `Categorized ${result.transactions_processed} transactions, ${result.categories_updated} updated`,
        'success'
      );
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Failed to categorize statement', 'error');
    } finally {
      setCategorizing(false);
    }
  };

  const metrics = status?.accuracy
    ? [
        { label: 'Overall Accuracy', value: `${(status.accuracy * 100).toFixed(1)}%`, color: '#4ADE80' },
        { label: 'Model Version', value: status.model_version || '—', color: '#60A5FA' },
        { label: 'Training Samples', value: status.training_samples?.toLocaleString() || '—', color: '#C9A96E' },
      ]
    : [
        { label: 'Overall Accuracy', value: '—', color: '#4ADE80' },
        { label: 'Model Version', value: '—', color: '#60A5FA' },
        { label: 'Training Samples', value: '—', color: '#C9A96E' },
      ];

  const categoryMetrics: CategoryMetric[] = status?.category_metrics || [];

  return (
    <section id="ml-training" className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        <div className="mb-6">
          <h2 className="font-serif text-[32px] text-text-primary">ML Model Management</h2>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Monitor categorization status and run keyword-based categorization on uploaded statements.
          </p>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-text-secondary text-sm">
            <Loader2 size={16} className="animate-spin" />
            Loading ML status...
          </div>
        ) : error ? (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20 mb-6">
            <AlertCircle size={16} />
            {error}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                {metrics.map(metric => (
                  <div key={metric.label} className="bg-surface border border-divider rounded-lg p-5">
                    <div className="font-mono text-[10px] uppercase text-text-secondary mb-2">{metric.label}</div>
                    <div className="font-mono text-[22px]" style={{ color: metric.color }}>{metric.value}</div>
                  </div>
                ))}
              </div>

              {categoryMetrics.length > 0 && (
                <div className="bg-surface border border-divider rounded-lg p-6">
                  <h3 className="font-sans text-sm font-medium text-text-primary mb-4">Category Breakdown</h3>
                  <div className="space-y-3">
                    {categoryMetrics.map((cat: CategoryMetric) => (
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
                            <div className="h-full rounded-full" style={{ width: `${cat.precision}%`, backgroundColor: 'rgba(96, 165, 250, 0.4)' }} />
                          </div>
                          <div className="flex-1 h-1.5 bg-canvas rounded-full overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${cat.recall}%`, backgroundColor: 'rgba(201, 169, 110, 0.4)' }} />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="bg-surface border border-divider rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <div className="font-sans text-sm font-medium text-text-primary">Incremental Training</div>
                    <div className="font-sans text-xs text-text-secondary mt-1">
                      {status?.message || 'ML categorizer is currently disabled by default.'}
                    </div>
                  </div>
                  <ToggleSwitch enabled={!!status?.enabled} onChange={handleToggle} />
                </div>
                <button
                  onClick={handleToggle}
                  disabled={toggling}
                  className="w-full mt-2 bg-gold text-canvas font-sans text-sm font-medium py-2.5 rounded-md transition-all duration-200 hover:bg-gold-hover disabled:opacity-50"
                >
                  {toggling ? 'Processing...' : 'Toggle ML / Refresh Status'}
                </button>
              </div>
            </div>

            <div className="space-y-4">
              <div className="bg-surface border border-divider rounded-lg p-6">
                <h3 className="font-sans text-sm font-medium text-text-primary mb-3">Run Categorization</h3>
                <p className="font-sans text-xs text-text-secondary mb-4">
                  Apply the keyword-based categorizer to all transactions in a statement.
                </p>
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={statementId}
                    onChange={(e) => setStatementId(e.target.value)}
                    placeholder="Statement ID"
                    className="flex-1 bg-canvas border border-divider rounded-md px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:border-gold focus:outline-none"
                  />
                  <button
                    onClick={handleCategorize}
                    disabled={categorizing}
                    className="flex items-center gap-2 bg-gold text-canvas font-sans text-sm font-medium px-4 py-2 rounded-md hover:bg-gold-hover transition-colors disabled:opacity-50"
                  >
                    {categorizing ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                    Run
                  </button>
                </div>
              </div>

              <div className="bg-surface border border-divider rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <span className="font-sans text-sm font-medium text-text-primary">Model Versions</span>
                  <button
                    onClick={() => setVersionsOpen(!versionsOpen)}
                    className="text-text-secondary hover:text-gold transition-colors"
                  >
                    {versionsOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>
                </div>

                {versionsOpen && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between py-2 border-t border-divider">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-sm text-gold">{status?.model_version || 'v3.8-production'}</span>
                        <span className="font-mono text-xs text-text-secondary">
                          {status?.last_trained ? new Date(status.last_trained).toLocaleString() : 'Not trained'}
                        </span>
                      </div>
                      <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400">
                        {status?.enabled ? 'Active' : 'Disabled'}
                      </span>
                    </div>
                    <p className="text-xs text-text-secondary">
                      <RotateCcw size={12} className="inline mr-1" />
                      Rollback and version switching require a trained model.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
