import { useEffect, useState, useRef, useCallback } from 'react';
import { TrendingUp, TrendingDown, DollarSign, AlertCircle, BarChart3 } from 'lucide-react';
import { getForecast } from '@/hooks/useAPI';
import { useClient } from '@/context/ClientContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
} from '@/components/ui/chart';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer,
  Area, AreaChart,
} from 'recharts';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface ForecastEntry {
  month: string;
  year_month: string;
  predicted_income: number;
  predicted_expenses: number;
  net: number;
}

interface ForecastData {
  client_id: number;
  months_ahead: number;
  methodology: string;
  entries: ForecastEntry[];
  total_predicted_income: number;
  total_predicted_expenses: number;
  total_net: number;
}

export default function ForecastPage() {
  const { selectedClient } = useClient();
  const sectionRef = useRef<HTMLDivElement>(null);

  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [monthsAhead, setMonthsAhead] = useState(12);

  const fetchData = useCallback(async () => {
    if (!selectedClient) return;
    setLoading(true);
    setError('');
    try {
      const data = await getForecast(selectedClient.id, monthsAhead);
      setForecast(data);
    } catch {
      setError('Failed to load forecast');
    } finally {
      setLoading(false);
    }
  }, [selectedClient, monthsAhead]);

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
  }, [loading, forecast]);

  const formatCurrency = (v: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Math.abs(v));

  const chartConfig = {
    income: { label: 'Income', color: '#10b981' },
    expenses: { label: 'Expenses', color: '#ef4444' },
    net: { label: 'Net', color: '#3b82f6' },
  };

  const chartData = forecast?.entries.map(e => ({
    month: e.month.slice(0, 3),
    income: e.predicted_income,
    expenses: e.predicted_expenses,
    net: e.net,
  })) || [];

  return (
    <section className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-8 gap-4">
          <div>
            <h1 className="font-serif text-3xl md:text-4xl text-text-primary flex items-center gap-3">
              <TrendingUp className="text-gold" size={28} />
              Forecast
            </h1>
            <p className="font-sans text-sm text-text-secondary mt-1">
              {forecast
                ? `Projected ${forecast.months_ahead}-month outlook (${forecast.methodology === 'recurring_templates' ? 'based on recurring templates' : 'based on 6-month historical average'})`
                : 'Project future income and expenses.'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label className="font-sans text-sm text-text-secondary">Months:</label>
            <select
              value={monthsAhead}
              onChange={e => setMonthsAhead(Number(e.target.value))}
              className="bg-surface border border-divider rounded-lg px-3 py-2 text-sm text-text-primary font-mono"
            >
              {[6, 12, 18, 24].map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
            <Button size="sm" variant="outline" onClick={fetchData}>
              Refresh
            </Button>
          </div>
        </div>

        {loading ? (
          <div className="text-text-secondary font-sans text-sm">Loading forecast...</div>
        ) : error ? (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20">
            <AlertCircle size={16} />{error}
          </div>
        ) : forecast ? (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
              <Card className="bg-surface border-divider">
                <CardHeader className="pb-2">
                  <CardTitle className="font-sans text-xs uppercase tracking-wide text-text-secondary flex items-center gap-2">
                    <TrendingUp size={14} className="text-emerald-400" />
                    Projected Income
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="font-mono text-2xl text-emerald-400">{formatCurrency(forecast.total_predicted_income)}</div>
                </CardContent>
              </Card>

              <Card className="bg-surface border-divider">
                <CardHeader className="pb-2">
                  <CardTitle className="font-sans text-xs uppercase tracking-wide text-text-secondary flex items-center gap-2">
                    <TrendingDown size={14} className="text-red-400" />
                    Projected Expenses
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="font-mono text-2xl text-red-400">{formatCurrency(forecast.total_predicted_expenses)}</div>
                </CardContent>
              </Card>

              <Card className="bg-surface border-divider">
                <CardHeader className="pb-2">
                  <CardTitle className="font-sans text-xs uppercase tracking-wide text-text-secondary flex items-center gap-2">
                    <DollarSign size={14} className="text-blue-400" />
                    Projected Net
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className={`font-mono text-2xl ${forecast.total_net >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {formatCurrency(forecast.total_net)}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Area Chart */}
            <Card className="bg-surface border-divider mb-8">
              <CardHeader>
                <CardTitle className="font-sans text-sm font-medium text-text-primary">Monthly Projection</CardTitle>
              </CardHeader>
              <CardContent>
                <ChartContainer config={chartConfig} className="h-[350px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-divider)" />
                      <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} />
                      <ChartTooltip content={<ChartTooltipContent formatter={(v: number) => formatCurrency(v)} />} />
                      <ChartLegend content={<ChartLegendContent />} />
                      <Area type="monotone" dataKey="income" stroke="var(--color-income)" fill="var(--color-income)" fillOpacity={0.15} strokeWidth={2} />
                      <Area type="monotone" dataKey="expenses" stroke="var(--color-expenses)" fill="var(--color-expenses)" fillOpacity={0.15} strokeWidth={2} />
                      <Line type="monotone" dataKey="net" stroke="var(--color-net)" strokeWidth={2} dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </ChartContainer>
              </CardContent>
            </Card>

            {/* Monthly Breakdown Table */}
            <Card className="bg-surface border-divider">
              <CardHeader>
                <CardTitle className="font-sans text-sm font-medium text-text-primary">Monthly Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[600px]">
                    <thead>
                      <tr className="border-b border-divider">
                        {['Month', 'Income', 'Expenses', 'Net'].map(h => (
                          <th key={h} className="font-mono text-[11px] uppercase text-text-secondary text-left px-4 py-3">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {forecast.entries.map((e, i) => (
                        <tr key={i} className="border-t border-divider hover:bg-surface-hover/50 transition-colors">
                          <td className="font-sans text-sm text-text-primary px-4 py-3">{e.month}</td>
                          <td className="font-mono text-sm text-emerald-400 px-4 py-3">{formatCurrency(e.predicted_income)}</td>
                          <td className="font-mono text-sm text-red-400 px-4 py-3">{formatCurrency(e.predicted_expenses)}</td>
                          <td className={`font-mono text-sm px-4 py-3 ${e.net >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {e.net >= 0 ? '+' : '-'}{formatCurrency(e.net)}
                          </td>
                        </tr>
                      ))}
                      <tr className="border-t-2 border-divider font-medium">
                        <td className="font-sans text-sm text-text-primary px-4 py-3">Total</td>
                        <td className="font-mono text-sm text-emerald-400 px-4 py-3">{formatCurrency(forecast.total_predicted_income)}</td>
                        <td className="font-mono text-sm text-red-400 px-4 py-3">{formatCurrency(forecast.total_predicted_expenses)}</td>
                        <td className={`font-mono text-sm px-4 py-3 ${forecast.total_net >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {formatCurrency(forecast.total_net)}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </>
        ) : (
          <div className="bg-surface border border-divider rounded-lg p-8 text-center">
            <BarChart3 size={32} className="text-text-secondary mx-auto mb-3" />
            <p className="text-text-secondary font-sans text-sm">No forecast data available.</p>
          </div>
        )}
      </div>
    </section>
  );
}
