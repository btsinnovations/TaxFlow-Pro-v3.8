import { useState, useEffect } from 'react';
import { X, Save } from 'lucide-react';
import { createClient, updateClient } from '@/hooks/useAPI';

interface ClientModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  client?: any;
}

export default function ClientModal({ isOpen, onClose, onSuccess, client }: ClientModalProps) {
  const [name, setName] = useState('');
  const [entityType, setEntityType] = useState('Individual');
  const [taxId, setTaxId] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (client) {
      setName(client.name || '');
      setEntityType(client.entity_type || 'Individual');
      setTaxId(client.tax_id || '');
      setNotes(client.notes || '');
    } else {
      setName('');
      setEntityType('Individual');
      setTaxId('');
      setNotes('');
    }
    setError('');
  }, [client, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Client name is required');
      return;
    }
    setLoading(true);
    setError('');
    try {
      if (client) {
        await updateClient(client.id, { name, entity_type: entityType, tax_id: taxId, notes });
      } else {
        await createClient({ name, entity_type: entityType, tax_id: taxId, notes });
      }
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save client');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-surface border border-divider rounded-xl w-full max-w-md mx-4 p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-serif text-xl text-text-primary">
            {client ? 'Edit Client' : 'Add New Client'}
          </h3>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-white/5 transition-colors">
            <X size={18} className="text-text-secondary" />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block font-sans text-xs text-text-secondary mb-1.5">Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-canvas border border-divider rounded-lg px-3 py-2.5 text-sm text-text-primary focus:border-gold focus:outline-none"
              placeholder="Client or business name"
            />
          </div>

          <div>
            <label className="block font-sans text-xs text-text-secondary mb-1.5">Entity Type</label>
            <select
              value={entityType}
              onChange={(e) => setEntityType(e.target.value)}
              className="w-full bg-canvas border border-divider rounded-lg px-3 py-2.5 text-sm text-text-primary focus:border-gold focus:outline-none"
            >
              <option value="Individual">Individual</option>
              <option value="S-Corp">S-Corp</option>
              <option value="Partnership">Partnership</option>
              <option value="LLC">LLC</option>
              <option value="C-Corp">C-Corp</option>
            </select>
          </div>

          <div>
            <label className="block font-sans text-xs text-text-secondary mb-1.5">Tax ID (optional)</label>
            <input
              type="text"
              value={taxId}
              onChange={(e) => setTaxId(e.target.value)}
              className="w-full bg-canvas border border-divider rounded-lg px-3 py-2.5 text-sm text-text-primary focus:border-gold focus:outline-none"
              placeholder="XX-XXXXXXX"
            />
          </div>

          <div>
            <label className="block font-sans text-xs text-text-secondary mb-1.5">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="w-full bg-canvas border border-divider rounded-lg px-3 py-2.5 text-sm text-text-primary focus:border-gold focus:outline-none resize-none"
              placeholder="Additional notes..."
            />
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 border border-divider text-text-secondary font-sans text-sm rounded-lg hover:bg-white/5 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2.5 bg-gold text-black font-sans text-sm font-medium rounded-lg hover:bg-gold/90 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? 'Saving...' : (
                <>
                  <Save size={14} />
                  {client ? 'Update' : 'Create'}
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
