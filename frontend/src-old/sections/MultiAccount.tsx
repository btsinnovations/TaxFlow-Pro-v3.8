import { useEffect, useState, useRef } from 'react';
import { Link2, RefreshCw, Trash2, Plus, AlertTriangle, Clock, Building2 } from 'lucide-react';
import { getAccounts, deleteAccount, syncAccount, getClients } from '@/hooks/useAPI';
import AccountModal from '@/components/AccountModal';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const statusConfig: Record<string, { dot: string; text: string }> = {
  Connected: { dot: '#4ADE80', text: 'Connected' },
  Error: { dot: '#F87171', text: 'Error' },
  Pending: { dot: '#FBBF24', text: 'Pending' },
  Disconnected: { dot: '#8A8A8A', text: 'Disconnected' },
};

function getFragilityColor(score: number): string {
  if (score <= 20) return '#4ADE80';
  if (score <= 50) return '#FBBF24';
  if (score <= 75) return '#FB923C';
  return '#F87171';
}

function getFragilityLabel(score: number): string {
  if (score <= 20) return 'Stable';
  if (score <= 50) return 'Moderate';
  if (score <= 75) return 'Fragile';
  return 'Critical';
}

export default function MultiAccount() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [clients, setClients] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedClient, setSelectedClient] = useState('');
  const [syncing, setSyncing] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const sectionRef = useRef<HTMLDivElement>(null);

  const loadData = async () => {
    try {
      const [accData, cliData] = await Promise.all([getAccounts(), getClients()]);
      setAccounts(accData);
      setClients(cliData);
    } catch (err) {
      console.error('Failed to load accounts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
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

  const handleSync = async (accountId: string) => {
    setSyncing(accountId);
    try {
      await syncAccount(accountId);
      loadData();
    } catch (err) {
      console.error('Sync failed:', err);
    } finally {
      setSyncing(null);
    }
  };

  const handleDelete = async (accountId: string) => {
    try {
      await deleteAccount(accountId);
      setDeleteConfirm(null);
      loadData();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const getClientName = (clientId: string) => {
    const c = clients.find((c: any) => c.id === clientId);
    return c?.name || clientId;
  };

  return (
    <section id="accounts" className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-serif text-[32px] text-text-primary">Multi-Account</h2>
            <p className="font-sans text-sm text-text-secondary mt-1">
              Link and manage multiple bank accounts per client. Monitor fragility scores.
            </p>
          </div>
          <button
            onClick={() => {
              setSelectedClient(clients[0]?.id || '');
              setModalOpen(true);
            }}
            disabled={clients.length === 0}
            className="flex items-center gap-2 font-sans text-sm font-medium border border-gold text-gold bg-transparent px-5 py-2 rounded-md transition-all duration-200 hover:bg-gold-muted disabled:opacity-30"
          >
            <Plus size={16} />
            Link Account
          </button>
        </div>

        {loading ? (
          <div className="text-text-secondary font-sans text-sm">Loading accounts...</div>
        ) : accounts.length === 0 ? (
          <div className="bg-surface border border-divider rounded-lg p-8 text-center">
            <Link2 size={32} className="text-text-secondary mx-auto mb-3" />
            <p className="text-text-secondary font-sans text-sm mb-4">
              No linked accounts yet. Add a client first, then link their bank accounts.
            </p>
            <button
              onClick={() => {
                setSelectedClient(clients[0]?.id || '');
                setModalOpen(true);
              }}
              disabled={clients.length === 0}
              className="font-sans text-sm font-medium border border-gold text-gold bg-transparent px-5 py-2 rounded-md transition-all duration-200 hover:bg-gold-muted disabled:opacity-30"
            >
              Link First Account
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {accounts.map((account: any) => {
              const status = statusConfig[account.status] || statusConfig['Disconnected'];
              const fragColor = getFragilityColor(account.fragility_score || 0);
              const fragLabel = getFragilityLabel(account.fragility_score || 0);
              return (
                <div
                  key={account.id}
                  className="bg-surface border border-divider rounded-lg p-5 transition-all duration-200 hover:border-divider-active"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center">
                        <Building2 size={20} className="text-gold" />
                      </div>
                      <div>
                        <h3 className="font-sans text-sm font-medium text-text-primary">{account.nickname}</h3>
                        <p className="font-mono text-xs text-text-secondary">{account.institution}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: status.dot }} />
                      <span className="font-sans text-xs" style={{ color: status.dot }}>{status.text}</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <div className="bg-canvas border border-divider rounded-md p-2.5">
                      <p className="font-sans text-[10px] text-text-secondary uppercase mb-1">Type</p>
                      <p className="font-sans text-xs text-text-primary">{account.account_type}</p>
                    </div>
                    <div className="bg-canvas border border-divider rounded-md p-2.5">
                      <p className="font-sans text-[10px] text-text-secondary uppercase mb-1">Client</p>
                      <p className="font-sans text-xs text-text-primary truncate">{getClientName(account.client_id)}</p>
                    </div>
                    <div className="bg-canvas border border-divider rounded-md p-2.5">
                      <p className="font-sans text-[10px] text-text-secondary uppercase mb-1">Last 4</p>
                      <p className="font-mono text-xs text-text-primary">****{account.account_number_last4 || '—'}</p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2 flex-1">
                      <div className="flex-1 h-1.5 bg-canvas rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${Math.min((account.fragility_score || 0), 100)}%`,
                            backgroundColor: fragColor,
                          }}
                        />
                      </div>
                      <span className="font-mono text-xs" style={{ color: fragColor }}>
                        {account.fragility_score || 0}%
                      </span>
                    </div>
                    <span className="font-sans text-[10px] px-2 py-0.5 rounded ml-2" style={{ backgroundColor: `${fragColor}15`, color: fragColor }}>
                      {fragLabel}
                    </span>
                  </div>

                  <div className="flex items-center justify-between pt-3 border-t border-divider">
                    <div className="flex items-center gap-1.5 text-text-secondary">
                      <Clock size={12} />
                      <span className="font-mono text-[10px]">
                        {account.last_sync ? new Date(account.last_sync).toLocaleString() : 'Never synced'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleSync(account.id)}
                        disabled={syncing === account.id}
                        className="flex items-center gap-1.5 font-sans text-xs text-gold border border-gold/30 px-2.5 py-1 rounded hover:bg-gold/10 transition-colors disabled:opacity-50"
                      >
                        <RefreshCw size={12} className={syncing === account.id ? 'animate-spin' : ''} />
                        {syncing === account.id ? 'Syncing...' : 'Sync'}
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(account.id)}
                        className="p-1.5 rounded hover:bg-red-500/10 transition-colors"
                      >
                        <Trash2 size={14} className="text-red-400" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {deleteConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
            <div className="bg-surface border border-divider rounded-xl p-6 max-w-sm mx-4">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={18} className="text-amber-400" />
                <h3 className="font-sans text-sm font-medium text-text-primary">Remove Account?</h3>
              </div>
              <p className="text-text-secondary font-sans text-sm mb-4">
                This will unlink the account. Transaction history will remain in the audit trail.
              </p>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setDeleteConfirm(null)}
                  className="flex-1 py-2 border border-divider text-text-secondary font-sans text-sm rounded-lg hover:bg-white/5"
                >
                  Cancel
                </button>
                <button
                  onClick={() => handleDelete(deleteConfirm)}
                  className="flex-1 py-2 bg-red-500/20 text-red-400 font-sans text-sm rounded-lg hover:bg-red-500/30 border border-red-500/30"
                >
                  Unlink
                </button>
              </div>
            </div>
          </div>
        )}

        <AccountModal
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          onSuccess={loadData}
          clientId={selectedClient}
          clients={clients}
        />
      </div>
    </section>
  );
}
