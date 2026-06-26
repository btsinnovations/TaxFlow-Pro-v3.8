import { useState, useEffect, useRef } from 'react';
import { Search, Loader2, AlertCircle, FileText, CheckCircle2, XCircle } from 'lucide-react';
import { searchTaxRules } from '@/hooks/useAPI';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface TaxRule {
  id: string;
  name: string;
  pattern: string;
  form?: string;
  line?: string;
  gl_account_id: number;
  priority: number;
  enabled: boolean;
  category: string;
}

const sortOptions = [
  { value: 'priority,desc', label: 'Priority (high → low)' },
  { value: 'priority,asc', label: 'Priority (low → high)' },
  { value: 'created_at,desc', label: 'Newest first' },
  { value: 'pattern_length,desc', label: 'Longest pattern first' },
];

function RuleSkeleton() {
  return (
    <div className="bg-surface border border-divider rounded-md p-4 animate-pulse">
      <div className="h-3 bg-canvas rounded w-1/3 mb-2" />
      <div className="h-2 bg-canvas rounded w-3/4" />
    </div>
  );
}

export default function TaxRules() {
  const { user } = useAuth();
  const [rules, setRules] = useState<TaxRule[]>([]);
  const [selectedRule, setSelectedRule] = useState<TaxRule | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [form, setForm] = useState('');
  const [line, setLine] = useState('');
  const [enabledFilter, setEnabledFilter] = useState<'all' | 'true' | 'false'>('all');
  const [sort, setSort] = useState('priority,desc');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);

  const loadRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sortField, sortOrder] = sort.split(',');
      const params: Parameters<typeof searchTaxRules>[0] = {
        query: searchQuery || undefined,
        form: form || undefined,
        line: line || undefined,
        sort: sortField,
        order: sortOrder,
      };
      if (enabledFilter !== 'all') {
        params.enabled = enabledFilter === 'true';
      }
      const data = await searchTaxRules(params);
      const normalized: TaxRule[] = (data || []).map((rule: any): TaxRule => ({
        id: String(rule.id || rule.rule_id || Math.random()),
        name: rule.name || 'Unnamed Rule',
        pattern: rule.pattern || '',
        form: rule.form,
        line: rule.line,
        gl_account_id: rule.gl_account_id ?? 0,
        priority: rule.priority ?? 0,
        enabled: rule.enabled ?? true,
        category: rule.category || 'Deductions',
      }));
      setRules(normalized);
      if (normalized.length > 0 && (!selectedRule || !normalized.find((r) => r.id === selectedRule.id))) {
        setSelectedRule(normalized[0]);
      }
      if (normalized.length === 0) setSelectedRule(null);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch tax rules');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRules();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, sort, enabledFilter]);

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
  }, []);

  return (
    <section id="tax-rules" className="bg-canvas px-4 md:px-8 py-8">
      <div className="max-w-[1440px] mx-auto">
        <div className="mb-6">
          <h2 className="font-serif text-[32px] text-text-primary">Tax Rules Engine</h2>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Search and filter categorization rules by name, tax form, line, and priority.
          </p>
        </div>

        {error && (
          <div className="mb-4 flex items-center gap-2 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 text-sm text-red-400">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div ref={leftRef} className="lg:col-span-3 space-y-4">
            <div className="flex flex-col md:flex-row gap-3">
              <div className="relative flex-1">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
                <Input
                  type="text"
                  placeholder="Search name or pattern..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && loadRules()}
                  className="pl-10 border-gold/30 bg-canvas text-text-primary"
                />
              </div>
              <Button onClick={loadRules} disabled={loading} className="bg-gold text-black hover:bg-gold/90">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                Search
              </Button>
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
              <Input
                placeholder="Form (e.g. Schedule C)"
                value={form}
                onChange={(e) => setForm(e.target.value)}
                className="border-gold/30 bg-canvas text-text-primary"
              />
              <Input
                placeholder="Line (e.g. line_1)"
                value={line}
                onChange={(e) => setLine(e.target.value)}
                className="border-gold/30 bg-canvas text-text-primary"
              />
              <Select value={enabledFilter} onValueChange={(v) => setEnabledFilter(v as any)}>
                <SelectTrigger className="border-gold/30 bg-canvas text-text-primary">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="true">Enabled only</SelectItem>
                  <SelectItem value="false">Disabled only</SelectItem>
                </SelectContent>
              </Select>
              <Select value={sort} onValueChange={(v) => setSort(v)}>
                <SelectTrigger className="border-gold/30 bg-canvas text-text-primary">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {sortOptions.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              {loading ? (
                <>
                  <RuleSkeleton />
                  <RuleSkeleton />
                  <RuleSkeleton />
                </>
              ) : rules.length === 0 ? (
                <div className="bg-surface border border-divider rounded-md p-6 text-center">
                  <p className="font-sans text-sm text-text-secondary">No rules match your filters.</p>
                  {searchQuery || form || line ? (
                    <Button variant="ghost" onClick={() => { setSearchQuery(''); setForm(''); setLine(''); setEnabledFilter('all'); }} className="text-gold mt-2">
                      Clear filters
                    </Button>
                  ) : null}
                </div>
              ) : (
                rules.map((rule) => (
                  <button
                    key={rule.id}
                    onClick={() => setSelectedRule(rule)}
                    className="w-full text-left bg-surface border rounded-md p-4 transition-all duration-200 hover:border-divider-active"
                    style={{
                      borderColor: selectedRule?.id === rule.id ? '#C9A96E' : '#2A2A2A',
                      borderLeftWidth: selectedRule?.id === rule.id ? '3px' : '1px',
                      borderLeftColor: selectedRule?.id === rule.id ? '#C9A96E' : '#2A2A2A',
                    }}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-sans text-sm font-medium text-text-primary">{rule.name}</span>
                      <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded ${rule.enabled ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'}`}>
                        {rule.enabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                    <p className="font-sans text-xs text-text-secondary truncate">{rule.pattern}</p>
                    <div className="flex gap-2 mt-2">
                      {rule.form ? <span className="font-mono text-[10px] text-gold bg-gold/10 px-1.5 py-0.5 rounded">{rule.form}</span> : null}
                      {rule.line ? <span className="font-mono text-[10px] text-text-secondary bg-white/5 px-1.5 py-0.5 rounded">{rule.line}</span> : null}
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          <div ref={rightRef} className="lg:col-span-2">
            <div className="bg-surface border border-divider rounded-lg p-6 sticky top-20">
              {!selectedRule ? (
                <div className="text-center py-8">
                  <p className="font-sans text-sm text-text-secondary">Select a rule to view details.</p>
                </div>
              ) : (
                <>
                  <div className="flex items-center gap-2 mb-4">
                    <FileText className="w-5 h-5 text-gold" />
                    <h3 className="font-serif text-xl text-text-primary">{selectedRule.name}</h3>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Rule ID</div>
                      <div className="font-mono text-sm text-text-primary">{selectedRule.id}</div>
                    </div>
                    <div>
                      <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Priority</div>
                      <div className="font-sans text-sm text-text-primary">{selectedRule.priority}</div>
                    </div>
                    <div>
                      <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Form</div>
                      <div className="font-sans text-sm text-text-primary">{selectedRule.form || '—'}</div>
                    </div>
                    <div>
                      <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Line</div>
                      <div className="font-sans text-sm text-text-primary">{selectedRule.line || '—'}</div>
                    </div>
                    <div>
                      <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">GL Account</div>
                      <div className="font-sans text-sm text-text-primary">{selectedRule.gl_account_id}</div>
                    </div>
                    <div>
                      <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Category</div>
                      <div className="font-sans text-sm text-text-primary">{selectedRule.category}</div>
                    </div>
                    <div>
                      <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Status</div>
                      <div className="flex items-center gap-1 text-sm">
                        {selectedRule.enabled ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-amber-400" />}
                        <span className={selectedRule.enabled ? 'text-emerald-400' : 'text-amber-400'}>
                          {selectedRule.enabled ? 'Enabled' : 'Disabled'}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4">
                    <div className="font-mono text-[10px] uppercase text-text-secondary mb-1">Pattern</div>
                    <div className="font-mono text-xs text-text-primary bg-canvas border border-divider rounded p-2 break-all">
                      {selectedRule.pattern}
                    </div>
                  </div>

                  <div className="flex gap-3 mt-6">
                    <button className="flex-1 bg-gold text-canvas font-sans text-sm font-medium py-2.5 rounded-md transition-all duration-200 hover:bg-gold-hover">
                      Edit Rule
                    </button>
                    <button className="flex-1 border border-gold text-gold bg-transparent font-sans text-sm font-medium py-2.5 rounded-md transition-all duration-200 hover:bg-gold-muted">
                      Test Rule
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
