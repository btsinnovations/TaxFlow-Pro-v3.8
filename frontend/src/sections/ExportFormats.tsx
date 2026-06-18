import { useEffect, useState, useRef } from 'react';
import { FileOutput, Table, Grid3x3, FileText, Braces, FileCheck, Download, AlertCircle } from 'lucide-react';
import { getExportFormats } from '@/hooks/useAPI';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const iconMap: Record<string, React.ElementType> = {
  FileOutput,
  Table,
  Grid3x3,
  FileText,
  Braces,
  FileCheck,
};

export default function ExportFormats() {
  const [formats, setFormats] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getExportFormats();
        setFormats(data);
      } catch (err) {
        setError('Failed to load export formats');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  useEffect(() => {
    if (loading) return;
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
  }, [loading]);

  return (
    <section id="export" className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        <div className="mb-6">
          <h2 className="font-serif text-[32px] text-text-primary">Export Formats</h2>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Download processed data in the format that works for your workflow.
          </p>
        </div>

        {loading ? (
          <div className="text-text-secondary font-sans text-sm">Loading formats...</div>
        ) : error ? (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20">
            <AlertCircle size={16} />
            {error}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {formats.map((fmt) => {
              const Icon = iconMap[fmt.icon] || FileText;
              const isAvailable = fmt.status === 'Available' || fmt.status === 'ready';
              return (
                <div
                  key={fmt.id}
                  className={`bg-surface border rounded-lg p-5 transition-all duration-200 ${
                    isAvailable
                      ? 'border-divider hover:border-gold/50 hover:bg-surface-hover'
                      : 'border-divider/50 opacity-60'
                  }`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: `${fmt.color}15` }}
                    >
                      <Icon size={20} style={{ color: fmt.color }} />
                    </div>
                    <div>
                      <h3 className="font-sans text-sm font-medium text-text-primary">{fmt.name}</h3>
                      <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded ${
                        isAvailable ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'
                      }`}>
                        {fmt.status}
                      </span>
                    </div>
                  </div>
                  <p className="font-sans text-xs text-text-secondary leading-relaxed mb-4">
                    {fmt.description}
                  </p>
                  {isAvailable && (
                    <button className="flex items-center gap-1.5 font-sans text-xs text-gold border border-gold/30 px-3 py-1.5 rounded hover:bg-gold/10 transition-colors">
                      <Download size={12} />
                      Available
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
