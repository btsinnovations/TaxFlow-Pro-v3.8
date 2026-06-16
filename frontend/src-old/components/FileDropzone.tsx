import { useState, useCallback } from 'react';
import { Upload, File, X, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

interface FileDropzoneProps {
  onUpload: (files: File[]) => Promise<void>;
  accept?: string;
  maxSizeMB?: number;
}

const FileDropzone = ({ onUpload, accept = ".pdf,.csv", maxSizeMB = 50 }: FileDropzoneProps) => {
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploaded, setUploaded] = useState<string[]>([]);
  const [errors, setErrors] = useState<string[]>([]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setIsDragging(true);
    } else if (e.type === 'dragleave') {
      setIsDragging(false);
    }
  }, []);

  const validateFile = (file: File): string | null => {
    const ext = file.name.toLowerCase();
    if (!ext.endsWith('.pdf') && !ext.endsWith('.csv')) {
      return `${file.name}: Only PDF and CSV files are supported.`;
    }
    if (file.size > maxSizeMB * 1024 * 1024) {
      return `${file.name}: File exceeds ${maxSizeMB}MB limit.`;
    }
    return null;
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    const validFiles: File[] = [];
    const newErrors: string[] = [];

    droppedFiles.forEach(file => {
      const error = validateFile(file);
      if (error) {
        newErrors.push(error);
      } else {
        validFiles.push(file);
      }
    });

    if (newErrors.length) setErrors(newErrors);
    if (validFiles.length) setFiles(prev => [...prev, ...validFiles]);
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    const validFiles: File[] = [];
    const newErrors: string[] = [];

    selected.forEach(file => {
      const error = validateFile(file);
      if (error) {
        newErrors.push(error);
      } else {
        validFiles.push(file);
      }
    });

    if (newErrors.length) setErrors(newErrors);
    if (validFiles.length) setFiles(prev => [...prev, ...validFiles]);
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (!files.length) return;
    setUploading(true);
    setErrors([]);
    try {
      await onUpload(files);
      setUploaded(files.map(f => f.name));
      setFiles([]);
    } catch (err) {
      setErrors([err instanceof Error ? err.message : 'Upload failed']);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="w-full">
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-xl p-8 text-center transition-all
          ${isDragging 
            ? 'border-[#C9A96E] bg-[#C9A96E]/5' 
            : 'border-white/20 bg-white/[0.02] hover:border-white/40'
          }
        `}
      >
        <input
          type="file"
          multiple
          accept={accept}
          onChange={handleFileInput}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
        <Upload className={`w-10 h-10 mx-auto mb-4 ${isDragging ? 'text-[#C9A96E]' : 'text-white/30'}`} />
        <p className="text-white/70 font-medium mb-1">
          Drop PDF or CSV statements here
        </p>
        <p className="text-white/40 text-sm">
          or click to browse • Max {maxSizeMB}MB per file
        </p>
      </div>

      {errors.length > 0 && (
        <div className="mt-4 space-y-2">
          {errors.map((err, i) => (
            <div key={i} className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 px-3 py-2 rounded-lg">
              <AlertCircle className="w-4 h-4" />
              {err}
            </div>
          ))}
        </div>
      )}

      {files.length > 0 && (
        <div className="mt-4 space-y-2">
          {files.map((file, i) => (
            <div key={i} className="flex items-center justify-between bg-white/5 px-4 py-3 rounded-lg border border-white/10">
              <div className="flex items-center gap-3">
                <File className="w-5 h-5 text-[#C9A96E]" />
                <div>
                  <p className="text-white text-sm font-medium">{file.name}</p>
                  <p className="text-white/40 text-xs">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
              </div>
              <button
                onClick={() => removeFile(i)}
                className="text-white/40 hover:text-red-400 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}

          <button
            onClick={handleUpload}
            disabled={uploading}
            className="w-full mt-4 py-3 bg-[#C9A96E] text-black font-medium rounded-lg hover:bg-[#B8975E] transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {uploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                Process {files.length} File{files.length > 1 ? 's' : ''}
              </>
            )}
          </button>
        </div>
      )}

      {uploaded.length > 0 && (
        <div className="mt-4 space-y-2">
          {uploaded.map((name, i) => (
            <div key={i} className="flex items-center gap-2 text-emerald-400 text-sm bg-emerald-400/10 px-3 py-2 rounded-lg">
              <CheckCircle className="w-4 h-4" />
              {name} processed successfully
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FileDropzone;
