import { useEffect, useState, useRef } from 'react';
import { Download, FileCheck, Clock, AlertCircle, ChevronDown } from 'lucide-react';
import { getProcessedFiles, exportStatement, getExportFormats } from '@/hooks/useAPI';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

interface ProcessedFile {
  file_id: string;
  filename: string;
  institution?: string;
  transaction_count?: number;
  processed_at?: string;
  status: 'completed' | 'uploaded';
}

interface ExportFormat {
  id: string;
  name: string;
  description?: string;
}

export default function ProcessedFiles() {
  const [files, setFiles] = useState<ProcessedFile[]>([]);
  const [exportFormats, setExportFormats] = useState<ExportFormat[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState('');
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [fileData, formatData] = await Promise.all([
          getProcessedFiles(),
          getExportFormats().catch(() => []),
        ]);
        setFiles(fileData);
        setExportFormats(formatData);
      } catch {
        setError('Failed to load processed files');
      } finally {
        setLoading(false);
      }
    };
    load();
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
  }, [loading, files]);

  const getExtension = (formatId: string) => {
    if (['qbo', 'xero'].includes(formatId)) return 'csv';
    if (formatId === 'excel') return 'xlsx';
    return formatId;
  };

  const handleDownload = async (fileId: string, format: ExportFormat) => {
    setDownloading(`${fileId}:${format.id}`);
    try {
      const blob = await exportStatement(fileId, format.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `statement_${fileId}.${getExtension(format.id)}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <section id="processed-files" className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-serif text-[32px] text-text-primary">Processed Files</h2>
            <p className="font-sans text-sm text-text-secondary mt-1">
              Download previously processed statements and exports.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="text-text-secondary font-sans text-sm">Loading files...</div>
        ) : error ? (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-4 rounded-lg border border-red-400/20">
            <AlertCircle size={16} />
            {error}
          </div>
        ) : files.length === 0 ? (
          <div className="bg-surface border border-divider rounded-lg p-8 text-center">
            <FileCheck size={32} className="text-text-secondary mx-auto mb-3" />
            <p className="text-text-secondary font-sans text-sm">
              No processed files yet. Upload a statement to get started.
            </p>
          </div>
        ) : (
          <div className="bg-surface border border-divider rounded-lg overflow-hidden">
            <table className="w-full min-w-[700px]">
              <thead>
                <tr className="bg-surface">
                  {['File ID', 'Filename', 'Institution', 'Transactions', 'Processed', 'Status', 'Actions'].map(h => (
                    <th key={h} className="font-mono text-[11px] uppercase text-text-secondary text-left px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {files.map((file, i) => (
                  <tr key={i} className="border-t border-divider hover:bg-surface-hover transition-colors duration-150">
                    <td className="font-mono text-xs text-gold px-4 py-3">{file.file_id}</td>
                    <td className="font-sans text-sm text-text-primary px-4 py-3">{file.filename}</td>
                    <td className="font-sans text-sm text-text-primary px-4 py-3">{file.institution || '—'}</td>
                    <td className="font-sans text-sm text-text-primary px-4 py-3">
                      {file.transaction_count !== undefined ? file.transaction_count.toLocaleString() : '—'}
                    </td>
                    <td className="font-mono text-xs text-text-secondary px-4 py-3 whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <Clock size={12} />
                        {file.processed_at ? new Date(file.processed_at).toLocaleString() : '—'}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1.5 font-sans text-xs px-2.5 py-1 rounded ${
                        file.status === 'completed'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${file.status === 'completed' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                        {file.status === 'completed' ? 'Completed' : 'Uploaded'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button
                            disabled={file.status !== 'completed'}
                            className="flex items-center gap-1.5 font-sans text-xs text-gold border border-gold/30 px-3 py-1.5 rounded hover:bg-gold/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            <Download size={12} className={downloading?.startsWith(`${file.file_id}:`) ? 'animate-spin' : ''} />
                            {downloading?.startsWith(`${file.file_id}:`) ? 'Downloading...' : 'Download'}
                            <ChevronDown size={12} />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="bg-surface border-divider text-text-primary">
                          {exportFormats.length === 0 && (
                            <DropdownMenuItem disabled className="text-text-secondary">
                              No formats available
                            </DropdownMenuItem>
                          )}
                          {exportFormats.map((fmt) => (
                            <DropdownMenuItem
                              key={fmt.id}
                              onClick={() => handleDownload(file.file_id, fmt)}
                              disabled={downloading === `${file.file_id}:${fmt.id}`}
                              className="hover:bg-surface-hover focus:bg-surface-hover cursor-pointer"
                            >
                              <Download size={12} className="text-gold" />
                              {fmt.name}
                            </DropdownMenuItem>
                          ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
