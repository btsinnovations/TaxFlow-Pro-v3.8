import { useState, useEffect, useRef } from 'react';
import { Play, ChevronDown, ChevronUp, Beaker, Microscope, Receipt, FileOutput, Shield, Brain } from 'lucide-react';
import { getTests, runTests } from '@/hooks/useAPI';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';


gsap.registerPlugin(ScrollTrigger);

interface TestResult {
  name: string;
  category: string;
  status: 'PASS' | 'FAIL' | 'SKIP';
  duration: string;
  details: string;
}

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

function formatDuration(seconds?: number): string {
  if (seconds == null || Number.isNaN(seconds)) return '—';
  return seconds < 1 ? `${(seconds * 1000).toFixed(0)}ms` : `${seconds.toFixed(2)}s`;
}

function normalizeTests(data: any): TestResult[] {
  if (!data) return [];
  if (Array.isArray(data)) {
    return data.map((t: any, i: number) => ({
      name: t.name || `test-${i}`,
      category: t.category || 'Parser',
      status: ['PASS', 'FAIL', 'SKIP'].includes(t.status) ? t.status : 'SKIP',
      duration: formatDuration(t.duration ?? t.runtime),
      details: t.details || t.message || t.stdout || 'No details',
    }));
  }
  if (data.stdout) {
    // /tests/run returns raw pytest output
    return [{
      name: 'pytest runner',
      category: 'Parser',
      status: data.passed ? 'PASS' : 'FAIL',
      duration: formatDuration(data.elapsed),
      details: data.stdout || data.stderr || 'Pytest run complete',
    }];
  }
  return [];
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
        <span className="font-mono text-sm text-text-primary flex-1">{test.name}</span>
        <span className="font-mono text-[10px] text-text-secondary w-16">{test.category}</span>
        <span
          className="font-mono text-[10px] px-2 py-0.5 rounded"
          style={{ backgroundColor: statusConfig[test.status].bg, color: statusConfig[test.status].text }}
        >
          {test.status}
        </span>
        <span className="font-mono text-xs text-text-secondary w-14 text-right">{test.duration}</span>
        {expanded ? <ChevronUp size={14} className="text-text-secondary" /> : <ChevronDown size={14} className="text-text-secondary" />}
      </button>
      {expanded && (
        <div className="px-4 pb-3 pl-12">
          <div className="bg-canvas border border-divider rounded-md p-3 font-mono text-xs text-text-secondary">
            {test.details}
          </div>
        </div>
      )}
    </div>
  );
}

function TestSkeleton() {
  return (
    <div className="flex items-center gap-4 px-4 py-3 border-t border-divider animate-pulse">
      <div className="w-4 h-4 bg-canvas rounded" />
      <div className="flex-1 h-3 bg-canvas rounded" />
      <div className="w-16 h-3 bg-canvas rounded" />
      <div className="w-14 h-3 bg-canvas rounded" />
    </div>
  );
}

export default function TestSuite() {
  const [tests, setTests] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [filter, setFilter] = useState('All');
  const [lastRun, setLastRun] = useState<string | null>(null);
  const sectionRef = useRef<HTMLDivElement>(null);

  const loadTests = async () => {
    try {
      setLoading(true);
      const data = await getTests();
      setTests(normalizeTests(data));
      setError(null);
      setLastRun(new Date().toLocaleString());
    } catch (err: any) {
      setError(err.message || 'Failed to load tests');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTests();
    const ctx = gsap.context(() => {
      gsap.fromTo(sectionRef.current, { opacity: 0, y: 30 }, {
        opacity: 1, y: 0, duration: 0.5, ease: 'power3.out',
        scrollTrigger: { trigger: sectionRef.current, start: 'top 80%', toggleActions: 'play none none none' },
      });
    });
    return () => ctx.revert();
  }, []);

  const handleRun = async (_hint?: string) => {
    try {
      setRunning(true);
      // Filter hints are advisory until a filter-aware endpoint exists.
      await runTests();
      await loadTests();
    } catch (err: any) {
      setError(err.message || 'Failed to run tests');
    } finally {
      setRunning(false);
    }
  };

  const passed = tests.filter(t => t.status === 'PASS').length;
  const failed = tests.filter(t => t.status === 'FAIL').length;
  const skipped = tests.filter(t => t.status === 'SKIP').length;

  const filtered = filter === 'All' ? tests : tests.filter(t => t.category === filter);

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

        {error && (
          <div className="mb-4 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <button
            onClick={() => handleRun('all')}
            disabled={running || loading}
            className="flex items-center gap-2 bg-gold text-canvas font-sans text-sm font-medium px-6 py-2.5 rounded-md transition-all duration-200 hover:bg-gold-hover disabled:opacity-50"
          >
            <Play size={14} />
            Run All Tests
          </button>
          <button
            onClick={() => handleRun('parser')}
            disabled={running || loading}
            className="font-sans text-sm font-medium border border-gold text-gold bg-transparent px-5 py-2 rounded-md transition-all duration-200 hover:bg-gold-muted disabled:opacity-50"
          >
            Run Parsers Only
          </button>
          <button
            onClick={() => handleRun('ml')}
            disabled={running || loading}
            className="font-sans text-sm font-medium border border-gold text-gold bg-transparent px-5 py-2 rounded-md transition-all duration-200 hover:bg-gold-muted disabled:opacity-50"
          >
            Run ML Tests
          </button>
          <button
            onClick={() => handleRun('tax')}
            disabled={running || loading}
            className="font-sans text-sm font-medium border border-gold text-gold bg-transparent px-5 py-2 rounded-md transition-all duration-200 hover:bg-gold-muted disabled:opacity-50"
          >
            Run Tax Rules
          </button>
          <span className="font-mono text-xs text-success ml-auto">
            {lastRun ? `Last run: ${lastRun} — ${passed} passed, ${failed} failed, ${skipped} skipped` : 'Loading...'}
          </span>
        </div>

        {/* Filter Tabs */}
        <div className="flex flex-wrap gap-2 mb-4">
          {['All', 'Parser', 'ML', 'Tax Rule', 'Export', 'Fragility', 'Security'].map(cat => (
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
          {loading ? (
            <>
              <TestSkeleton />
              <TestSkeleton />
              <TestSkeleton />
            </>
          ) : filtered.length === 0 ? (
            <div className="px-4 py-6 text-center">
              <p className="font-sans text-sm text-text-secondary">No test results available.</p>
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
