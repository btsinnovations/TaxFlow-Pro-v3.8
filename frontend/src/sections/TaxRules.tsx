import { useState, useEffect, useRef } from 'react';
import { Search, Loader2, AlertCircle } from 'lucide-react';
import { getCategories } from '@/hooks/useAPI';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface TaxCategory {
  code: string;
  name: string;
  schedule: string;
  line: string;
}

const scheduleConfig: Record<string, { bg: string; text: string }> = {
  C: { bg: 'rgba(96, 165, 250, 0.15)', text: '#60A5FA' },
  E: { bg: 'rgba(74, 222, 128, 0.15)', text: '#4ADE80' },
  A: { bg: 'rgba(251, 191, 36, 0.15)', text: '#FBBF24' },
  SE: { bg: 'rgba(201, 169, 110, 0.15)', text: '#C9A96E' },
  '': { bg: 'rgba(138, 138, 138, 0.15)', text: '#8A8A8A' },
};

const scheduleTabs = ['All', 'C', 'E', 'A', 'SE'];

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

export default function TaxRules() {
  const [categories, setCategories] = useState<TaxCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<TaxCategory | null>(null);
  const [activeSchedule, setActiveSchedule] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCodes, setActiveCodes] = useState<Set<string>>(new Set());
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getCategories();
        setCategories(data);
        if (data.length > 0) setSelected(data[0]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load categories');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  useEffect(() => {
    const ctx = gsap.context(() => {
      if (leftRef.current) {
        gsap.fromTo(leftRef.current, { opacity: 0, x: -20 }, {
          opacity: 1, x: 0, duration: 0.5, ease: 'power3.out',
          scrollTrigger: { trigger: leftRef.current, start: 'top 80%', toggleActions: 'play none none none' },
        });
      }
      if (rightRef.current) {
        gsap.fromTo(rightRef.current, { opacity: 0, x: 20 }, {
          opacity: 1, x: 0, duration: 0.5, ease: 'power3.out',
          scrollTrigger: { trigger: rightRef.current, start: 'top 80%', toggleActions: 'play none none none' },
        });
      }
    });
    return () => ctx.revert();
  }, [loading, categories]);

  const filtered = categories.filter(rule => {
    const matchesSchedule = activeSchedule === 'All' || rule.schedule === activeSchedule;
    const q = searchQuery.toLowerCase();
    const matchesSearch = !q || rule.name.toLowerCase().includes(q) || rule.code.toLowerCase().includes(q);
    return matchesSchedule && matchesSearch;
  });

  const toggleActive = (code: string) => {
    setActiveCodes(prev => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  return (
    <section id="tax-rules" className="bg-canvas px-4 md:px-8 py-8">
      <div className="max-w-[1440px] mx-auto">
        <div className="mb-6">
          <h2 className="font-serif text-[32px] text-text-primary">Tax Categories</h2>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Browse IRS schedule categories used for transaction classification and tax reporting.
          </p>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-text-secondary text-sm">
            <Loader2 size={16} className="animate-spin" />
            Loading categories...
          </div>
        ) : error ? (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20">
            <AlertCircle size={16} />
            {error}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            <div ref={leftRef} className="lg:col-span-3 space-y-4">
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
                <input
                  type="text"
                  placeholder="Search categories..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-surface border border-divider rounded-md pl-10 pr-4 py-2.5 font-sans text-sm text-text-primary placeholder:text-text-secondary focus:border-gold focus:outline-none transition-colors"
                />
              </div>

              <div className="flex flex-wrap gap-2">
                {scheduleTabs.map(tab => (
                  <button
                    key={tab}
                    onClick={() => setActiveSchedule(tab)}
                    className="font-mono text-[11px] uppercase tracking-wide px-3 py-1.5 rounded transition-all duration-200"
                    style={{
                      backgroundColor: activeSchedule === tab ? 'rgba(201, 169, 110, 0.15)' : 'transparent',
                      color: activeSchedule === tab ? '#C9A96E' : '#8A8A8A',
                    }}
                  >
                    {tab === 'All' ? 'All' : `Schedule ${tab}`}
                  </button>
                ))}
              </div>

              <div className="space-y-2">
                {filtered.map(category => (
                  <button
                    key={category.code}
                    onClick={() => setSelected(category)}
                    className="w-full text-left bg-surface border rounded-md p-4 transition-all duration-200 hover:border-divider-active"
                    style={{
                      borderColor: selected?.code === category.code ? '#C9A96E' : '#2A2A2A',
                      borderLeftWidth: selected?.code === category.code ? '3px' : '1px',
                      borderLeftColor: selected?.code === category.code ? '#C9A96E' : '#2A2A2A',
                    }}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-sans text-sm font-medium text-text-primary">{category.name}</span>
                      {category.schedule && (
                        <span
                          className="font-mono text-[10px] px-1.5 py-0.5 rounded"
                          style={{
                            backgroundColor: scheduleConfig[category.schedule]?.bg,
                            color: scheduleConfig[category.schedule]?.text,
                          }}
                        >
                          Schedule {category.schedule}
                        </span>
                      )}
                    </div>
                    <p className="font-mono text-xs text-text-secondary">{category.code}</p>
                  </button>
                ))}
                {filtered.length === 0 && (
                  <div className="text-text-secondary text-sm py-4">No categories match your filters.</div>
                )}
              </div>
            </div>

            <div ref={rightRef} className="lg:col-span-2">
              {selected && (
                <div className="bg-surface border border-divider rounded-lg p-6 sticky top-20">
                  <h3 className="font-serif text-xl text-text-primary mb-4">{selected.name}</h3>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Code</div>
                      <div className="font-mono text-sm text-text-primary">{selected.code}</div>
                    </div>
                    <div>
                      <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Schedule</div>
                      <div className="font-sans text-sm text-text-primary">{selected.schedule || '—'}</div>
                    </div>
                    <div>
                      <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Form Line</div>
                      <div className="font-sans text-sm text-text-primary">{selected.line || '—'}</div>
                    </div>
                    <div>
                      <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Active</div>
                      <ToggleSwitch enabled={activeCodes.has(selected.code)} onChange={() => toggleActive(selected.code)} />
                    </div>
                  </div>

                  <div className="flex gap-3 mt-6">
                    <button
                      onClick={() => toggleActive(selected.code)}
                      className="flex-1 bg-gold text-canvas font-sans text-sm font-medium py-2.5 rounded-md transition-all duration-200 hover:bg-gold-hover"
                    >
                      {activeCodes.has(selected.code) ? 'Deactivate' : 'Activate'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
