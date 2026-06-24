import { useState, useEffect } from 'react';
import { X, Save, Building2 } from 'lucide-react';
import { createAccount } from '@/hooks/useAPI';

interface AccountModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  clientId: string;
  clients: any[];
}

export default function AccountModal({ isOpen, onClose, onSuccess, clientId, clients }: AccountModalProps) {
  const [selectedClient, setSelectedClient] = useState(clientId);
  const [nickname, setNickname] = useState('');
  const [institution, setInstitution] = useState('');
  const [accountType, setAccountType] = useState('Checking');
  const [last4, setLast4] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen) {
      setSelectedClient(clientId || (clients[0]?.id || ''));
      setNickname('');
      setInstitution('');
      setAccountType('Checking');
      setLast4('');
      setNotes('');
      setError('');
    }
  }, [isOpen, clientId, clients]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nickname.trim() || !institution.trim() || !selectedClient) {
      setError('Nickname, institution, and client are required');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await createAccount({
        client_id: selectedClient,
        nickname,
        institution,
        account_type: accountType,
        account_number_last4: last4 || undefined,
        notes: notes || undefined,
      });
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create account');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-surface border border-divider rounded-xl w-full max-w-md mx-4 p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-serif text-xl text-text-primary">Link Bank Account</h3>
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
            <label className="block font-sans text-xs text-text-secondary mb-1.5">Client *</label>
            <select
              value={selectedClient}
              onChange={(e) => setSelectedClient(e.target.value)}
              className="w-full bg-canvas border border-divider rounded-lg px-3 py-2.5 text-sm text-text-primary focus:border-gold focus:outline-none"
            >
              <option value="">Select client...</option>
              {clients.map((c: any) => (
                <option key={c.id} value={c.id}>{c.name} ({c.entity_type})</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block font-sans text-xs text-text-secondary mb-1.5">Account Nickname *</label>
            <input
              type="text"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              className="w-full bg-canvas border border-divider rounded-lg px-3 py-2.5 text-sm text-text-primary focus:border-gold focus:outline-none"
              placeholder="e.g., Primary Checking"
            />
          </div>

          <div>
            <label className="block font-sans text-xs text-text-secondary mb-1.5">Institution *</label>
            <div className="relative">
              <Building2 size={14} className="absolute left-3 top-3 text-text-secondary" />
              <input
                type="text"
                value={institution}
                onChange={(e) => setInstitution(e.target.value)}
                className="w-full bg-canvas border border-divider rounded-lg pl-9 pr-3 py-2.5 text-sm text-text-primary focus:border-gold focus:outline-none"
                placeholder="e.g., TD Bank, Chase, Chime"
              />
            </div>
          </div>

          <div>
            <label className="block font-sans text-xs text-text-secondary mb-1.5">Account Type</label>
            <select
              value={accountType}
              onChange={(e) => setAccountType(e.target.value)}
              className="w-full bg-canvas border border-divider rounded-lg px-3 py-2.5 text-sm text-text-primary focus:border-gold focus:outline-none"
            >
              <option value="Checking">Checking</option>
              <option value="Savings">Savings</option>
              <option value="Credit">Credit Card</option>
              <option value="Investment">Investment</option>
              <option value="Loan">Loan</option>
            </select>
          </div>

          <div>
            <label className="block font-sans text-xs text-text-secondary mb-1.5">Last 4 Digits (optional)</label>
            <input
              type="text"
              value={last4}
              onChange={(e) => setLast4(e.target.value.replace(/\\D/g, '').slice(0, 4))}
              maxLength={4}
              className="w-full bg-canvas border border-divider rounded-lg px-3 py-2.5 text-sm text-text-primary focus:border-gold focus:outline-none"
              placeholder="1234"
            />
          </div>

          <div>
            <label className="block font-sans text-xs text-text-secondary mb-1.5">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
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
              {loading ? 'Linking...' : (
                <>
                  <Save size={14} />
                  Link Account
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
