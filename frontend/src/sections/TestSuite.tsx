import { useState, useEffect, useRef } from 'react';
import { Play, ChevronDown, ChevronUp, Beaker, Microscope, Receipt, FileOutput, Shield, Brain, Loader2 } from 'lucide-react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { getTests, runTests } from '@/hooks/useAPI';

gsap.registerPlugin(ScrollTrigger);

const statusConfig = {
  PASS: { bg: 'rgba(74, 222, 128, 0.15)', text: '#4ADE80' },
  FAIL: { bg: 'rgba(248, 113, 113, 0.15)', text: '#F87171' },
  SKIP: { bg: 'rgba(251, 191, 36, 0.15)', text: '#FBBF24' },
};

const categoryIcons: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  Parser: Beaker,
  ML: Brain,
  'Tax Rule': Receipt,
  Export: FileOutput,
  Fragility: Microscope,
  Security: Shield,
};

interface TestResult {
  name: string;
  category: string;
  status: 'PASS' | 'FAIL' | 'SKIP';
  duration: string;
  details: string;
}

function TestRow({ test }: { test: TestResult }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = categoryIcons[test.category] || Beaker;

  return (
    <div className="border-t border-divider">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-4 px-4 py-3 hover:bg-surface-hover transition-colors text-left"
      >
        <Icon size={14} className="text-text-secondary flex-shrink-0" />
        <span className="font-mono text-sm text-text-primary flex-1 truncate" title={test.name}>{test.name}</span>
        <span className="font-mono text-[10px] text-text-secondary w-16">{test.category}</span>
        <span
          className="font-mono text-[10px] px-2 py-0.5 rounded"
          style={{ backgroundColor: statusConfig[test.status].bg, color: statusConfig[test.status].text }}
        >
          {test.status}
        </span>
        <span className="font-mono text-xs text-text-secondary w-14 text-right">{test.duration || '—'}</span>
        {expanded ? <ChevronUp size={14} className="text-text-secondary" /> : <ChevronDown size={14} className="text-text-secondary" />}
      </button>
      {expanded && test.details && (
        <div className="px-4 pb-3 pl-12">
          <div className="bg-canvas border border-divider rounded-md p-3 font-mono text-xs text-text-secondary whitespace-pre-wrap">
            {test.details}
          </div>
        </div>
      )}
    </div>
  );
}

const CATEGORIES = ['All', 'Parser', 'ML', 'Tax Rule', 'Export', 'Fragility', 'Security'];

export default function TestSuite() {
  const [filter, setFilter] = useState('All');
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<string>('—');
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo(sectionRef.current, { opacity: 0, y: 30 }, {
        opacity: 1, y: 0, duration: 0.5, ease: 'power3.out',
        scrollTrigger: { trigger: sectionRef.current, start: 'top 80%', toggleActions: 'play none none none' },
      });
    });
    return () => ctx.revert();
  }, []);

  const loadTests = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getTests();
      setResults(Array.isArray(data.results) ? data.results : []);
      setLastRun(data.last_run || new Date().toISOString());
    } catch (err: any) {
      setError(err?.message || 'Failed to load test results');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTests();
  }, []);

  const handleRunAll = async () => {
    setRunning(true);
    setError(null);
    try {
      await runTests();
      await loadTests();
    } catch (err: any) {
      setError(err?.message || 'Failed to run tests');
    } finally {
      setRunning(false);
    }
  };

  const passed = results.filter(t => t.status === 'PASS').length;
  const failed = results.filter(t => t.status === 'FAIL').length;
  const skipped = results.filter(t => t.status === 'SKIP').length;

  const filtered = filter === 'All' ? results : results.filter(t => t.category === filter);

  const formatLastRun = (iso: string) => {
    if (iso === '—') return iso;
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  return (
    <section id="test-suite" className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h2 className="font-serif text-[32px] text-text-primary">Automated Test Suite</h2>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Continuous validation of parsers, categorizers, tax rules, and export pipelines.
          </p>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <button
            onClick={handleRunAll}
            disabled={running}
            className="flex items-center gap-2 bg-gold text-canvas font-sans text-sm font-medium px-6 py-2.5 rounded-md transition-all duration-200 hover:bg-gold-hover disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            Run All Tests
          </button>
          <span className="font-mono text-xs text-success ml-auto">
            Last run: {formatLastRun(lastRun)} — {passed} passed, {failed} failed, {skipped} skipped
          </span>
        </div>

        {/* Filter Tabs */}
        <div className="flex flex-wrap gap-2 mb-4">
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => setFilter(cat)}
              className="font-mono text-[11px] uppercase tracking-wide px-3 py-1.5 rounded transition-all duration-200"
              style={{
                backgroundColor: filter === cat ? 'rgba(201, 169, 110, 0.15)' : 'transparent',
                color: filter === cat ? '#C9A96E' : '#8A8A8A',
              }}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Status messages */}
        {loading && (
          <div className="flex items-center gap-2 text-text-secondary font-sans text-sm mb-4">
            <Loader2 size={16} className="animate-spin" />
            Loading test results…
          </div>
        )}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 font-sans text-sm p-3 rounded-md mb-4">
            {error}
          </div>
        )}

        {/* Test Results */}
        <div className="bg-surface border border-divider rounded-lg overflow-hidden">
          <div className="flex items-center gap-4 px-4 py-3 border-b border-divider">
            <span className="font-mono text-[10px] uppercase text-text-secondary w-4" />
            <span className="font-mono text-[10px] uppercase text-text-secondary flex-1">Test Name</span>
            <span className="font-mono text-[10px] uppercase text-text-secondary w-16">Category</span>
            <span className="font-mono text-[10px] uppercase text-text-secondary w-16">Status</span>
            <span className="font-mono text-[10px] uppercase text-text-secondary w-14 text-right">Duration</span>
            <span className="font-mono text-[10px] uppercase text-text-secondary w-4" />
          </div>
          {!loading && filtered.length === 0 ? (
            <div className="px-4 py-8 text-center text-text-secondary font-sans text-sm">
              No tests found{filter !== 'All' ? ` for category “${filter}”` : ''}.
            </div>
          ) : (
            filtered.map((test, i) => (
              <TestRow key={i} test={test} />
            ))
          )}
        </div>
      </div>
    </section>
  );
}
