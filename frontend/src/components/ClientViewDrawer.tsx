import { X, FileText, Calendar, Shield } from 'lucide-react';

interface ClientViewDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  client: any;
}

export default function ClientViewDrawer({ isOpen, onClose, client }: ClientViewDrawerProps) {
  if (!isOpen || !client) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-full max-w-md bg-surface border-l border-divider h-full overflow-y-auto p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-serif text-xl text-text-primary">Client Details</h3>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-white/5 transition-colors">
            <X size={18} className="text-text-secondary" />
          </button>
        </div>

        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <Shield size={20} className="text-gold" />
            <div>
              <p className="font-sans text-sm text-text-primary font-medium">{client.name}</p>
              <p className="font-mono text-xs text-text-secondary">{client.id}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-canvas border border-divider rounded-lg p-3">
              <p className="font-sans text-xs text-text-secondary mb-1">Entity Type</p>
              <p className="font-sans text-sm text-text-primary">{client.entity_type}</p>
            </div>
            <div className="bg-canvas border border-divider rounded-lg p-3">
              <p className="font-sans text-xs text-text-secondary mb-1">Status</p>
              <p className="font-sans text-sm text-emerald-400">{client.status || 'Active'}</p>
            </div>
          </div>

          <div className="bg-canvas border border-divider rounded-lg p-3">
            <p className="font-sans text-xs text-text-secondary mb-1">Tax ID</p>
            <p className="font-sans text-sm text-text-primary">{client.tax_id || 'Not provided'}</p>
          </div>

          <div className="bg-canvas border border-divider rounded-lg p-3">
            <p className="font-sans text-xs text-text-secondary mb-1">Notes</p>
            <p className="font-sans text-sm text-text-primary">{client.notes || 'No notes'}</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-canvas border border-divider rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <FileText size={14} className="text-text-secondary" />
                <p className="font-sans text-xs text-text-secondary">Documents</p>
              </div>
              <p className="font-mono text-lg text-text-primary">{client.documents_processed || 0}</p>
            </div>
            <div className="bg-canvas border border-divider rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <Calendar size={14} className="text-text-secondary" />
                <p className="font-sans text-xs text-text-secondary">Created</p>
              </div>
              <p className="font-sans text-sm text-text-primary">
                {client.created_at ? new Date(client.created_at).toLocaleDateString() : '—'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
