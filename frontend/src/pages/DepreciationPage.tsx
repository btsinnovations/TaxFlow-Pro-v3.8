import { useEffect, useState, useRef } from 'react';
import { Calculator, AlertCircle, ChevronRight, FileText, Table2 } from 'lucide-react';
import { calculateDepreciation, getDepreciationMethods, getMacrsTables } from '@/hooks/useAPI';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Collapsible, CollapsibleContent, CollapsibleTrigger,
} from '@/components/ui/collapsible';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface DepreciationMethod {
  code: string;
  name: string;
  description: string;
}

interface ScheduleEntry {
  year: number;
  beginning_basis: number;
  deduction: number;
  ending_basis: number;
  method: string;
}

interface DepreciationResult {
  asset_name: string;
  asset_class: string;
  cost_basis: number;
  recovery_period: number;
  method: string;
  business_use_pct: number;
  section_179_expense: number;
  bonus_depreciation: number;
  depreciable_basis: number;
  total_deduction: number;
  schedule: ScheduleEntry[];
}

const METHOD_DESCRIPTIONS: Record<string, string> = {
  macrs_hy: 'Modified Accelerated Cost Recovery System with half-year convention',
  macrs_mq: 'MACRS with mid-quarter convention for Q4 assets',
  straight_line: 'Equal annual deductions over recovery period',
  section_179: 'Immediate expensing up to annual limit (2024: $1,250,000)',
  bonus_60: '60% first-year bonus depreciation for 2025 qualifying property',
};

export default function DepreciationPage() {
  const sectionRef = useRef<HTMLDivElement>(null);

  const [methods, setMethods] = useState<DepreciationMethod[]>([]);
  const [macrsTables, setMacrsTables] = useState<Record<string, any> | null>(null);
  const [showMacrsTables, setShowMacrsTables] = useState(false);

  // Calculator form
  const [form, setForm] = useState({
    asset_name: '',
    asset_class: '5',
    cost_basis: '',
    placed_in_service_date: '',
    recovery_period: '5',
    method: 'macrs_hy',
    section_179_expense: '0',
    bonus_depreciation_pct: '0',
    salvage_value: '0',
    business_use_pct: '100',
  });

  const [result, setResult] = useState<DepreciationResult | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getDepreciationMethods().then(setMethods).catch(() => {});
    getMacrsTables().then(setMacrsTables).catch(() => {});
  }, []);

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
  }, [result]);

  const formatCurrency = (v: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Math.abs(v));

  const handleCalculate = async () => {
    if (!form.asset_name || !form.cost_basis || !form.placed_in_service_date) {
      setError('Asset name, cost basis, and placed-in-service date are required.');
      return;
    }
    setCalculating(true);
    setError('');
    try {
      const data = await calculateDepreciation({
        asset_name: form.asset_name,
        asset_class: form.asset_class,
        cost_basis: parseFloat(form.cost_basis),
        placed_in_service_date: form.placed_in_service_date,
        recovery_period: parseFloat(form.recovery_period),
        method: form.method,
        section_179_expense: parseFloat(form.section_179_expense) || 0,
        bonus_depreciation_pct: parseFloat(form.bonus_depreciation_pct) || 0,
        salvage_value: parseFloat(form.salvage_value) || 0,
        business_use_pct: parseFloat(form.business_use_pct) || 100,
      });
      setResult(data);
    } catch (e: any) {
      setError(e.message || 'Failed to calculate depreciation');
    } finally {
      setCalculating(false);
    }
  };

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
            <Calculator className="text-gold" size={28} />
            Depreciation Calculator
          </h1>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Calculate depreciation schedules using MACRS, straight-line, Section 179, and bonus methods.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Calculator Form */}
          <Card className="bg-surface border-divider lg:col-span-1">
            <CardHeader>
              <CardTitle className="font-sans text-sm font-medium text-text-primary">Asset Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="font-sans text-xs text-text-secondary">Asset Name</Label>
                <Input
                  value={form.asset_name}
                  onChange={e => setForm(f => ({ ...f, asset_name: e.target.value }))}
                  placeholder="e.g. MacBook Pro"
                  className="bg-canvas border-divider text-sm"
                />
              </div>
              <div>
                <Label className="font-sans text-xs text-text-secondary">Asset Class (Recovery Period)</Label>
                <Select value={form.asset_class} onValueChange={v => setForm(f => ({ ...f, asset_class: v, recovery_period: v }))}>
                  <SelectTrigger className="bg-canvas border-divider text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="3">3-Year (special)</SelectItem>
                    <SelectItem value="5">5-Year (computers, autos)</SelectItem>
                    <SelectItem value="7">7-Year (furniture, equipment)</SelectItem>
                    <SelectItem value="10">10-Year (agricultural)</SelectItem>
                    <SelectItem value="15">15-Year (land improvements)</SelectItem>
                    <SelectItem value="20">20-Year (farm buildings)</SelectItem>
                    <SelectItem value="27.5">27.5-Year (residential rental)</SelectItem>
                    <SelectItem value="39">39-Year (commercial real estate)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="font-sans text-xs text-text-secondary">Cost Basis ($)</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={form.cost_basis}
                  onChange={e => setForm(f => ({ ...f, cost_basis: e.target.value }))}
                  placeholder="0.00"
                  className="bg-canvas border-divider text-sm"
                />
              </div>
              <div>
                <Label className="font-sans text-xs text-text-secondary">Placed in Service Date</Label>
                <Input
                  type="date"
                  value={form.placed_in_service_date}
                  onChange={e => setForm(f => ({ ...f, placed_in_service_date: e.target.value }))}
                  className="bg-canvas border-divider text-sm"
                />
              </div>
              <div>
                <Label className="font-sans text-xs text-text-secondary">Method</Label>
                <Select value={form.method} onValueChange={v => setForm(f => ({ ...f, method: v }))}>
                  <SelectTrigger className="bg-canvas border-divider text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {methods.map(m => (
                      <SelectItem key={m.code} value={m.code}>{m.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {METHOD_DESCRIPTIONS[form.method] && (
                  <p className="font-sans text-[11px] text-text-secondary mt-1">{METHOD_DESCRIPTIONS[form.method]}</p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="font-sans text-xs text-text-secondary">Section 179 ($)</Label>
                  <Input
                    type="number"
                    value={form.section_179_expense}
                    onChange={e => setForm(f => ({ ...f, section_179_expense: e.target.value }))}
                    className="bg-canvas border-divider text-sm"
                  />
                </div>
                <div>
                  <Label className="font-sans text-xs text-text-secondary">Bonus Deprec. (%)</Label>
                  <Input
                    type="number"
                    value={form.bonus_depreciation_pct}
                    onChange={e => setForm(f => ({ ...f, bonus_depreciation_pct: e.target.value }))}
                    className="bg-canvas border-divider text-sm"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="font-sans text-xs text-text-secondary">Salvage Value ($)</Label>
                  <Input
                    type="number"
                    value={form.salvage_value}
                    onChange={e => setForm(f => ({ ...f, salvage_value: e.target.value }))}
                    className="bg-canvas border-divider text-sm"
                  />
                </div>
                <div>
                  <Label className="font-sans text-xs text-text-secondary">Business Use (%)</Label>
                  <Input
                    type="number"
                    value={form.business_use_pct}
                    onChange={e => setForm(f => ({ ...f, business_use_pct: e.target.value }))}
                    className="bg-canvas border-divider text-sm"
                  />
                </div>
              </div>
              <Button className="w-full bg-gold text-black hover:bg-gold/90" onClick={handleCalculate} disabled={calculating}>
                {calculating ? 'Calculating...' : 'Calculate Depreciation'}
              </Button>
            </CardContent>
          </Card>

          {/* Results */}
          <div className="lg:col-span-2 space-y-4">
            {error && (
              <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20">
                <AlertCircle size={16} />{error}
              </div>
            )}

            {result && (
              <>
                {/* Summary Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-surface border border-divider rounded-lg p-3">
                    <div className="font-sans text-[10px] uppercase tracking-wide text-text-secondary">Cost Basis</div>
                    <div className="font-mono text-lg text-text-primary">{formatCurrency(result.cost_basis)}</div>
                  </div>
                  <div className="bg-surface border border-divider rounded-lg p-3">
                    <div className="font-sans text-[10px] uppercase tracking-wide text-text-secondary">Depreciable Basis</div>
                    <div className="font-mono text-lg text-gold">{formatCurrency(result.depreciable_basis)}</div>
                  </div>
                  <div className="bg-surface border border-divider rounded-lg p-3">
                    <div className="font-sans text-[10px] uppercase tracking-wide text-text-secondary">Section 179</div>
                    <div className="font-mono text-lg text-blue-400">{formatCurrency(result.section_179_expense)}</div>
                  </div>
                  <div className="bg-surface border border-divider rounded-lg p-3">
                    <div className="font-sans text-[10px] uppercase tracking-wide text-text-secondary">Total Deduction</div>
                    <div className="font-mono text-lg text-emerald-400">{formatCurrency(result.total_deduction)}</div>
                  </div>
                </div>

                {/* Method badges */}
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline" className="text-xs border-gold/30 text-gold capitalize">{result.method.replace('_', ' ')}</Badge>
                  <Badge variant="outline" className="text-xs border-text-secondary/30 text-text-secondary">{result.recovery_period}-year property</Badge>
                  <Badge variant="outline" className="text-xs border-text-secondary/30 text-text-secondary">{result.business_use_pct}% business use</Badge>
                  {result.bonus_depreciation > 0 && (
                    <Badge variant="outline" className="text-xs border-blue-400/30 text-blue-400">Bonus: {formatCurrency(result.bonus_depreciation)}</Badge>
                  )}
                </div>

                {/* Schedule Table */}
                <Card className="bg-surface border-divider">
                  <CardHeader>
                    <CardTitle className="font-sans text-sm font-medium text-text-primary flex items-center gap-2">
                      <Table2 size={16} className="text-gold" />
                      Depreciation Schedule — {result.asset_name}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[500px]">
                        <thead>
                          <tr className="border-b border-divider">
                            {['Year', 'Beginning Basis', 'Deduction', 'Ending Basis'].map(h => (
                              <th key={h} className="font-mono text-[11px] uppercase text-text-secondary text-left px-4 py-3">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {result.schedule.map((entry, i) => (
                            <tr key={i} className="border-t border-divider hover:bg-surface-hover/50 transition-colors">
                              <td className="font-mono text-sm text-text-primary px-4 py-3">{entry.year}</td>
                              <td className="font-mono text-sm text-text-secondary px-4 py-3">{formatCurrency(entry.beginning_basis)}</td>
                              <td className="font-mono text-sm text-emerald-400 px-4 py-3">{formatCurrency(entry.deduction)}</td>
                              <td className="font-mono text-sm text-text-primary px-4 py-3">{formatCurrency(entry.ending_basis)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              </>
            )}

            {!result && !error && (
              <Card className="bg-surface border-divider">
                <CardContent className="p-8 text-center">
                  <Calculator size={32} className="text-text-secondary mx-auto mb-3" />
                  <p className="text-text-secondary font-sans text-sm">Fill in asset details and click Calculate to generate a depreciation schedule.</p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>

        {/* MACRS Tables Reference */}
        {macrsTables && (
          <Collapsible open={showMacrsTables} onOpenChange={setShowMacrsTables} className="mt-8">
            <Card className="bg-surface border-divider">
              <CollapsibleTrigger asChild>
                <CardHeader className="cursor-pointer">
                  <CardTitle className="font-sans text-sm font-medium text-text-primary flex items-center gap-2">
                    <FileText size={16} className="text-gold" />
                    IRS MACRS Percentage Tables
                    <ChevronRight size={16} className={`text-text-secondary transition-transform ${showMacrsTables ? 'rotate-90' : ''}`} />
                  </CardTitle>
                </CardHeader>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {Object.entries(macrsTables).map(([key, table]: [string, any]) => (
                      <div key={key} className="bg-canvas rounded-lg p-4">
                        <div className="font-sans text-sm font-medium text-text-primary mb-2">{table.name}</div>
                        <div className="font-mono text-xs space-y-1">
                          {table.yearly_percentages.map((pct: number, i: number) => (
                            <div key={i} className="flex justify-between text-text-secondary">
                              <span>Year {i + 1}</span>
                              <span>{pct}%</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </CollapsibleContent>
            </Card>
          </Collapsible>
        )}
      </div>
    </section>
  );
}
