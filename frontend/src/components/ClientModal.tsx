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
        await updateClient(client.id, { name, tax_id: taxId });
      } else {
        await createClient({ name, tax_id: taxId });
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="bg-[#141414] border border-[#2A2A2A] rounded-xl w-full max-w-md mx-4 p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-serif text-xl text-[#F5F0E8]">
            {client ? 'Edit Client' : 'Add New Client'}
          </h3>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-white/10 transition-colors">
            <X size={18} className="text-[#8A8A8A]" />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block font-sans text-xs text-[#8A8A8A] mb-1.5">Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-[#0C0C0C] border border-[#2A2A2A] rounded-lg px-3 py-2.5 text-sm text-[#F5F0E8] focus:border-[#C9A96E] focus:outline-none"
              placeholder="Client or business name"
            />
          </div>

          <div>
            <label className="block font-sans text-xs text-[#8A8A8A] mb-1.5">Entity Type</label>
            <select
              value={entityType}
              onChange={(e) => setEntityType(e.target.value)}
              className="w-full bg-[#0C0C0C] border border-[#2A2A2A] rounded-lg px-3 py-2.5 text-sm text-[#F5F0E8] focus:border-[#C9A96E] focus:outline-none"
            >
              <option value="Individual">Individual</option>
              <option value="S-Corp">S-Corp</option>
              <option value="Partnership">Partnership</option>
              <option value="LLC">LLC</option>
              <option value="C-Corp">C-Corp</option>
            </select>
          </div>

          <div>
            <label className="block font-sans text-xs text-[#8A8A8A] mb-1.5">Tax ID (optional)</label>
            <input
              type="text"
              value={taxId}
              onChange={(e) => setTaxId(e.target.value)}
              className="w-full bg-[#0C0C0C] border border-[#2A2A2A] rounded-lg px-3 py-2.5 text-sm text-[#F5F0E8] focus:border-[#C9A96E] focus:outline-none"
              placeholder="XX-XXXXXXX"
            />
          </div>

          <div>
            <label className="block font-sans text-xs text-[#8A8A8A] mb-1.5">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="w-full bg-[#0C0C0C] border border-[#2A2A2A] rounded-lg px-3 py-2.5 text-sm text-[#F5F0E8] focus:border-[#C9A96E] focus:outline-none resize-none"
              placeholder="Additional notes..."
            />
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 border border-[#2A2A2A] text-[#8A8A8A] font-sans text-sm rounded-lg hover:bg-white/10 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2.5 bg-[#C9A96E] text-[#0C0C0C] font-sans text-sm font-medium rounded-lg hover:bg-[#B8975E] transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
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
