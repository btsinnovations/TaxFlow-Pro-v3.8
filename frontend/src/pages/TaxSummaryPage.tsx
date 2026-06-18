import { useEffect, useState, useRef } from 'react';
import { Receipt, TrendingUp, TrendingDown, DollarSign, AlertCircle, BarChart3 } from 'lucide-react';
import { getTaxSummary } from '@/hooks/useAPI';
import { useClient } from '@/context/ClientContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
} from '@/components/ui/chart';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from 'recharts';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface TaxSummary {
  year: number;
  total_income: number;
  total_expenses: number;
  net: number;
}

const CURRENT_YEAR = new Date().getFullYear();

export default function TaxSummaryPage() {
  useClient();
  const [year, setYear] = useState(CURRENT_YEAR);
  const [summary, setSummary] = useState<TaxSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const data = await getTaxSummary(year);
        setSummary(data);
      } catch {
        setError('Failed to load tax summary');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [year]);

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
  }, [loading, summary]);

  const formatCurrency = (v: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v);

  const netPct = summary && summary.total_income > 0
    ? ((summary.net / summary.total_income) * 100).toFixed(1)
    : '0.0';

  const chartData = summary ? [
    { name: 'Income', value: summary.total_income, fill: 'var(--color-income)' },
    { name: 'Expenses', value: summary.total_expenses, fill: 'var(--color-expenses)' },
    { name: 'Net', value: summary.net, fill: 'var(--color-net)' },
  ] : [];

  const chartConfig = {
    income: { label: 'Income', color: '#10b981' },
    expenses: { label: 'Expenses', color: '#ef4444' },
    net: { label: 'Net', color: '#3b82f6' },
  };

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-8 gap-4">
          <div>
            <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
              <Receipt className="text-gold" size={28} />
              Tax Summary
            </h1>
            <p className="font-sans text-sm text-text-secondary mt-1">
              Annual income, expenses, and net tax position overview.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label className="font-sans text-sm text-text-secondary">Tax Year:</label>
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="bg-surface border border-divider rounded-lg px-3 py-2 text-sm text-text-primary font-mono"
            >
              {Array.from({ length: 6 }, (_, i) => CURRENT_YEAR - i).map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
        </div>

        {loading ? (
          <div className="text-text-secondary font-sans text-sm">Loading tax summary...</div>
        ) : error ? (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20">
            <AlertCircle size={16} />
            {error}
          </div>
        ) : summary ? (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <Card className="bg-surface border-divider">
                <CardHeader className="pb-2">
                  <CardTitle className="font-sans text-xs uppercase tracking-wide text-text-secondary flex items-center gap-2">
                    <TrendingUp size={14} className="text-emerald-400" />
                    Total Income
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="font-mono text-2xl text-emerald-400">{formatCurrency(summary.total_income)}</div>
                </CardContent>
              </Card>

              <Card className="bg-surface border-divider">
                <CardHeader className="pb-2">
                  <CardTitle className="font-sans text-xs uppercase tracking-wide text-text-secondary flex items-center gap-2">
                    <TrendingDown size={14} className="text-red-400" />
                    Total Expenses
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="font-mono text-2xl text-red-400">{formatCurrency(summary.total_expenses)}</div>
                </CardContent>
              </Card>

              <Card className="bg-surface border-divider">
                <CardHeader className="pb-2">
                  <CardTitle className="font-sans text-xs uppercase tracking-wide text-text-secondary flex items-center gap-2">
                    <DollarSign size={14} className="text-blue-400" />
                    Net Position
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className={`font-mono text-2xl ${summary.net >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {formatCurrency(summary.net)}
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-surface border-divider">
                <CardHeader className="pb-2">
                  <CardTitle className="font-sans text-xs uppercase tracking-wide text-text-secondary flex items-center gap-2">
                    <BarChart3 size={14} className="text-gold" />
                    Net Margin
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="font-mono text-2xl text-gold">{netPct}%</div>
                </CardContent>
              </Card>
            </div>

            {/* Chart + Breakdown */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card className="bg-surface border-divider">
                <CardHeader>
                  <CardTitle className="font-sans text-sm font-medium text-text-primary">Income vs Expenses</CardTitle>
                </CardHeader>
                <CardContent>
                  <ChartContainer config={chartConfig} className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-divider)" />
                        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                        <YAxis tick={{ fontSize: 12 }} tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} />
                        <ChartTooltip content={<ChartTooltipContent formatter={(v: any) => formatCurrency(Number(v))} />} />
                        <ChartLegend content={<ChartLegendContent />} />
                        <Bar dataKey="value" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </ChartContainer>
                </CardContent>
              </Card>

              <Card className="bg-surface border-divider">
                <CardHeader>
                  <CardTitle className="font-sans text-sm font-medium text-text-primary">{year} Tax Breakdown</CardTitle>
                </CardHeader>
                <CardContent>
                  <table className="w-full">
                    <tbody>
                      <tr className="border-t border-divider">
                        <td className="font-sans text-sm text-text-secondary py-3">Tax Year</td>
                        <td className="font-mono text-sm text-text-primary text-right py-3">{summary.year}</td>
                      </tr>
                      <tr className="border-t border-divider">
                        <td className="font-sans text-sm text-text-secondary py-3">Gross Income</td>
                        <td className="font-mono text-sm text-emerald-400 text-right py-3">{formatCurrency(summary.total_income)}</td>
                      </tr>
                      <tr className="border-t border-divider">
                        <td className="font-sans text-sm text-text-secondary py-3">Total Deductions</td>
                        <td className="font-mono text-sm text-red-400 text-right py-3">-{formatCurrency(summary.total_expenses)}</td>
                      </tr>
                      <tr className="border-t border-divider">
                        <td className="font-sans text-sm font-medium text-text-primary py-3">Net Taxable Income</td>
                        <td className={`font-mono text-sm text-right py-3 font-medium ${summary.net >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {formatCurrency(summary.net)}
                        </td>
                      </tr>
                      <tr className="border-t border-divider">
                        <td className="font-sans text-sm text-text-secondary py-3">Expense Ratio</td>
                        <td className="font-mono text-sm text-text-primary text-right py-3">
                          {summary.total_income > 0
                            ? ((summary.total_expenses / summary.total_income) * 100).toFixed(1)
                            : '0.0'}%
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            </div>
          </>
        ) : (
          <div className="bg-surface border border-divider rounded-lg p-8 text-center">
            <Receipt size={32} className="text-text-secondary mx-auto mb-3" />
            <p className="text-text-secondary font-sans text-sm">No tax data available for {year}.</p>
          </div>
        )}
      </div>
    </section>
  );
}
