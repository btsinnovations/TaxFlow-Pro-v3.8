import { useEffect, useState, useRef } from 'react';
import { FileOutput, Table, Grid3x3, FileText, Braces, FileCheck, Download, AlertCircle, Loader2 } from 'lucide-react';
import { getExportFormats, getProcessedFiles } from '@/hooks/useAPI';
import { Button } from '@/components/ui/button';
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
  const [processedCount, setProcessedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [exportingId, setExportingId] = useState<string | null>(null);
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [formatsData, files] = await Promise.all([
          getExportFormats(),
          getProcessedFiles(),
        ]);
        setFormats(formatsData);
        setProcessedCount(files.filter((f) => f.status === 'completed').length);
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

  const handleExport = async (fmtId: string) => {
    setExportingId(fmtId);
    // simulate brief progress; real export would call an endpoint and stream a download
    await new Promise((resolve) => setTimeout(resolve, 800));
    setExportingId(null);
  };

  const canExport = processedCount > 0;

  return (
    <section id="export" className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        <div className="mb-6">
          <h2 className="font-serif text-[32px] text-text-primary">Export Formats</h2>
          <p className="font-sans text-sm text-text-secondary mt-1">
            Download processed data in the format that works for your workflow.
          </p>
        </div>

        {!canExport && !loading && (
          <div className="mb-6 flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/10 p-4 text-sm text-amber-300">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <div>
              <p className="font-medium">No processed statements yet</p>
              <p className="text-amber-300/80">Upload and process a statement to enable downloads. Export formats become active once transactions are available.</p>
            </div>
          </div>
        )}

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
              const isAvailable = fmt.status === 'Available' && canExport;
              const isExporting = exportingId === fmt.id;
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
                        {isAvailable ? 'Available' : 'Locked'}
                      </span>
                    </div>
                  </div>
                  <p className="font-sans text-xs text-text-secondary leading-relaxed mb-4">
                    {fmt.description}
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!isAvailable || isExporting}
                    onClick={() => handleExport(fmt.id)}
                    className={`flex items-center gap-1.5 text-xs ${
                      isAvailable
                        ? 'border-gold/30 text-gold hover:bg-gold/10'
                        : 'border-divider text-text-secondary cursor-not-allowed'
                    }`}
                  >
                    {isExporting ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Download size={12} />
                    )}
                    {isExporting ? 'Exporting...' : isAvailable ? 'Download' : 'No data'}
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
