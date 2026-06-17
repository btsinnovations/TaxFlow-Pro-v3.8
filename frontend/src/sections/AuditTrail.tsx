import { useState, useEffect, useRef } from 'react';
import { Download, ChevronLeft, ChevronRight } from 'lucide-react';
import { getAuditLog } from '@/hooks/useAPI';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const severityColors: Record<string, string> = {
  INFO: '#60A5FA',
  WARNING: '#FBBF24',
  ERROR: '#F87171',
  CRITICAL: '#F87171',
};

const eventTypeConfig: Record<string, { bg: string; text: string }> = {
  PROCESS: { bg: 'rgba(74, 222, 128, 0.15)', text: '#4ADE80' },
  RULE_CHANGE: { bg: 'rgba(201, 169, 110, 0.15)', text: '#C9A96E' },
  USER_ACTION: { bg: 'rgba(96, 165, 250, 0.15)', text: '#60A5FA' },
  SYSTEM: { bg: 'rgba(251, 191, 36, 0.15)', text: '#FBBF24' },
  EXPORT: { bg: 'rgba(248, 113, 113, 0.15)', text: '#F87171' },
  FILE_UPLOAD: { bg: 'rgba(74, 222, 128, 0.15)', text: '#4ADE80' },
  PROCESSING_COMPLETE: { bg: 'rgba(74, 222, 128, 0.15)', text: '#4ADE80' },
  PROCESSING_FAILED: { bg: 'rgba(248, 113, 113, 0.15)', text: '#F87171' },
  ML_INIT_FAILED: { bg: 'rgba(251, 191, 36, 0.15)', text: '#FBBF24' },
};

const severityLevels = ['All Levels', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];

export default function AuditTrail() {
  const [severityFilter, setSeverityFilter] = useState('All Levels');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [auditEvents, setAuditEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const sectionRef = useRef<HTMLDivElement>(null);
  const pageSize = 8;

  useEffect(() => {
    const loadAudit = async () => {
      try {
        const data: any = await getAuditLog(100);
        const events = Array.isArray(data) ? data : data?.events ?? data?.logs ?? [];
        setAuditEvents(events);
      } catch (err) {
        console.error('Failed to load audit log:', err);
      } finally {
        setLoading(false);
      }
    };
    loadAudit();
  }, []);

  useEffect(() => {
    if (loading) return;
    const ctx = gsap.context(() => {
      gsap.fromTo(sectionRef.current, { opacity: 0, y: 30 }, {
        opacity: 1, y: 0, duration: 0.5, ease: 'power3.out',
        scrollTrigger: { trigger: sectionRef.current, start: 'top 80%', toggleActions: 'play none none none' },
      });
    });
    return () => ctx.revert();
  }, [loading]);

  const filtered = auditEvents.filter(event => {
    const matchesSeverity = severityFilter === 'All Levels' || event.severity === severityFilter;
    const matchesSearch = !searchQuery || event.description?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSeverity && matchesSearch;
  });

  const totalPages = Math.ceil(filtered.length / pageSize) || 1;
  const paginated = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  return (
    <section id="audit-log" className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-serif text-[32px] text-text-primary">Audit Trail</h2>
            <p className="font-sans text-sm text-text-secondary mt-1">
              Complete, immutable record of every processing event, rule change, and user action.
            </p>
          </div>
          <button className="hidden sm:flex items-center gap-2 border border-gold text-gold bg-transparent font-sans text-sm font-medium px-5 py-2 rounded-md transition-all duration-200 hover:bg-gold-muted">
            <Download size={14} />
            Export Log
          </button>
        </div>

        {loading ? (
          <div className="text-text-secondary font-sans text-sm">Loading audit log...</div>
        ) : (
          <>
            <div className="flex flex-wrap gap-3 mb-4">
              <input
                type="text"
                placeholder="From"
                className="bg-surface border border-divider rounded-md px-3 py-2 font-sans text-sm text-text-primary placeholder:text-text-secondary focus:border-gold focus:outline-none"
              />
              <input
                type="text"
                placeholder="To"
                className="bg-surface border border-divider rounded-md px-3 py-2 font-sans text-sm text-text-primary placeholder:text-text-secondary focus:border-gold focus:outline-none"
              />
              <select
                value={severityFilter}
                onChange={(e) => { setSeverityFilter(e.target.value); setCurrentPage(1); }}
                className="bg-surface border border-divider rounded-md px-3 py-2 font-sans text-sm text-text-primary focus:border-gold focus:outline-none"
              >
                {severityLevels.map(level => <option key={level} value={level}>{level}</option>)}
              </select>
              <input
                type="text"
                placeholder="Search events..."
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                className="bg-surface border border-divider rounded-md px-3 py-2 font-sans text-sm text-text-primary placeholder:text-text-secondary focus:border-gold focus:outline-none flex-1 min-w-[200px]"
              />
            </div>

            <div className="bg-surface border border-divider rounded-lg overflow-hidden overflow-x-auto">
              <table className="w-full min-w-[800px]">
                <thead>
                  <tr className="bg-surface">
                    {['Timestamp', 'Severity', 'Event Type', 'Client ID', 'Description', 'User', 'Session ID'].map(h => (
                      <th key={h} className="font-mono text-[11px] uppercase text-text-secondary text-left px-4 py-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {paginated.map((event, i) => (
                    <tr key={i} className="border-t border-divider hover:bg-surface-hover transition-colors duration-150">
                      <td className="font-mono text-xs text-text-secondary px-4 py-3 whitespace-nowrap">
                        {new Date(event.timestamp).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`w-2 h-2 rounded-full ${event.severity === 'CRITICAL' ? 'animate-pulse-dot' : ''}`}
                            style={{ backgroundColor: severityColors[event.severity] || '#8A8A8A' }}
                          />
                          <span className="font-sans text-xs" style={{ color: severityColors[event.severity] || '#8A8A8A' }}>{event.severity}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className="font-mono text-[10px] px-2 py-0.5 rounded"
                          style={{ backgroundColor: eventTypeConfig[event.event_type]?.bg || 'rgba(138,138,138,0.15)', color: eventTypeConfig[event.event_type]?.text || '#8A8A8A' }}
                        >
                          {event.event_type}
                        </span>
                      </td>
                      <td className="font-mono text-xs text-gold px-4 py-3">{event.client_id || '—'}</td>
                      <td className="font-sans text-sm text-text-primary px-4 py-3 max-w-[400px] truncate">{event.description}</td>
                      <td className="font-sans text-xs text-text-secondary px-4 py-3">{event.user}</td>
                      <td className="font-mono text-xs text-text-secondary px-4 py-3">{event.session_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between mt-4 px-2">
              <span className="font-mono text-xs text-text-secondary">
                Showing {Math.min((currentPage - 1) * pageSize + 1, filtered.length)}-{Math.min(currentPage * pageSize, filtered.length)} of {filtered.length} events
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="p-1.5 rounded hover:bg-surface-hover disabled:opacity-30 transition-opacity"
                >
                  <ChevronLeft size={16} className="text-text-secondary" />
                </button>
                {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map(page => (
                  <button
                    key={page}
                    onClick={() => setCurrentPage(page)}
                    className="font-mono text-xs px-2 py-1 rounded transition-colors"
                    style={{ color: currentPage === page ? '#C9A96E' : '#8A8A8A' }}
                  >
                    {page}
                  </button>
                ))}
                <button
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="p-1.5 rounded hover:bg-surface-hover disabled:opacity-30 transition-opacity"
                >
                  <ChevronRight size={16} className="text-text-secondary" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
