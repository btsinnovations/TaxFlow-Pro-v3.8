import { useEffect, useRef, useState } from 'react';
import { FileText, Users, Calculator, Brain } from 'lucide-react';
import { getDashboardStats, getAuditLog } from '@/hooks/useAPI';
import { log } from '@/lib/logger';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const statusColors: Record<string, string> = {
  Active: '#4ADE80',
  Idle: '#8A8A8A',
  Warning: '#FBBF24',
  Error: '#F87171',
};

const pipelineStages = [
  { name: 'PDF Ingestion', status: 'Active', throughput: 'Ready' },
  { name: 'OCR Extraction', status: 'Active', throughput: 'Ready' },
  { name: 'Transaction Parsing', status: 'Active', throughput: 'Ready' },
  { name: 'ML Categorization', status: 'Active', throughput: 'Ready' },
  { name: 'Tax Rule Engine', status: 'Active', throughput: 'Ready' },
  { name: 'Export Generation', status: 'Idle', throughput: '—' },
];

export default function DashboardOverview() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const cardsRef = useRef<HTMLDivElement[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [activity, setActivity] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [statsData, auditData] = await Promise.all([
          getDashboardStats(),
          getAuditLog(5),
        ]);
        setStats(statsData);
        setActivity(auditData);
      } catch (err) {
        log.error('Dashboard load failed:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  useEffect(() => {
    if (loading) return;
    const ctx = gsap.context(() => {
      cardsRef.current.forEach((card, i) => {
        if (!card) return;
        gsap.fromTo(
          card,
          { opacity: 0, y: 30 },
          {
            opacity: 1,
            y: 0,
            duration: 0.5,
            delay: i * 0.08,
            ease: 'power3.out',
            scrollTrigger: {
              trigger: sectionRef.current,
              start: 'top 80%',
              toggleActions: 'play none none none',
            },
          }
        );
      });
    }, sectionRef);

    return () => ctx.revert();
  }, [loading]);

  const statCards = stats ? [
    { label: 'Documents Processed', value: stats.total_documents?.toLocaleString() || '0', icon: FileText, change: 'Live count', changeColor: '#4ADE80' },
    { label: 'Active Clients', value: stats.total_clients?.toString() || '0', icon: Users, change: stats.pipeline_status || 'Unknown', changeColor: '#FBBF24' },
    { label: 'Tax Rules Applied', value: stats.total_transactions?.toLocaleString() || '0', icon: Calculator, change: stats.ml_status || 'Unknown', changeColor: '#4ADE80' },
    { label: 'ML Confidence', value: stats.ml_status || 'N/A', icon: Brain, change: stats.last_processing ? `Last: ${new Date(stats.last_processing).toLocaleDateString()}` : 'No recent processing', changeColor: '#4ADE80' },
  ] : [];

  return (
    <section id="dashboard" className="bg-canvas px-4 md:px-8 py-8" style={{ paddingTop: '88px' }}>
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        {loading ? (
          <div className="text-text-secondary font-sans text-sm">Loading dashboard...</div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              {statCards.map((stat, i) => (
                <div
                  key={stat.label}
                  ref={el => { if (el) cardsRef.current[i] = el; }}
                  className="bg-surface border border-divider rounded-lg p-6 transition-all duration-200 hover:border-divider-active hover:bg-surface-hover"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <stat.icon size={20} className="text-gold" />
                    <span className="font-sans text-sm text-text-secondary">{stat.label}</span>
                  </div>
                  <div className="font-mono text-[28px] text-text-primary mb-1">{stat.value}</div>
                  <div className="font-sans text-xs" style={{ color: stat.changeColor }}>{stat.change}</div>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-5 gap-6" id="pipeline">
              <div className="lg:col-span-3 bg-surface border border-divider rounded-lg p-6">
                <h3 className="font-sans text-base font-medium text-text-primary mb-4">Processing Pipeline</h3>
                <div className="space-y-2">
                  {pipelineStages.map(stage => (
                    <div
                      key={stage.name}
                      className="flex items-center justify-between bg-canvas border border-divider rounded-md px-4 py-3"
                    >
                      <span className="font-sans text-sm text-text-primary">{stage.name}</span>
                      <div className="flex items-center gap-6">
                        <div className="flex items-center gap-2">
                          <span
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: statusColors[stage.status] }}
                          />
                          <span className="font-sans text-xs" style={{ color: statusColors[stage.status] }}>
                            {stage.status}
                          </span>
                        </div>
                        <span className="font-mono text-xs text-text-secondary w-24 text-right">{stage.throughput}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="lg:col-span-2 bg-surface border border-divider rounded-lg p-6">
                <h3 className="font-sans text-base font-medium text-text-primary mb-4">Recent Activity</h3>
                <div className="space-y-4">
                  {activity.length === 0 ? (
                    <p className="text-text-secondary text-sm">No recent activity</p>
                  ) : (
                    activity.map((event, i) => (
                      <div key={i} className="border-l-2 border-gold pl-3">
                        <div className="font-mono text-[11px] text-text-secondary mb-0.5">
                          {new Date(event.timestamp).toLocaleString()}
                        </div>
                        <div className="font-sans text-[13px] text-text-primary leading-snug">{event.description}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
