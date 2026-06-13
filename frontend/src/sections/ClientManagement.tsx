import { useEffect, useRef, useState } from 'react';
import { Shield, Eye, Pencil, Trash2, Plus } from 'lucide-react';
import { getClients, deleteClient } from '@/hooks/useAPI';
import ClientModal from '@/components/ClientModal';
import ClientViewDrawer from '@/components/ClientViewDrawer';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const entityTypeConfig: Record<string, { bg: string; text: string }> = {
  Individual: { bg: 'rgba(96, 165, 250, 0.15)', text: '#60A5FA' },
  'S-Corp': { bg: 'rgba(74, 222, 128, 0.15)', text: '#4ADE80' },
  Partnership: { bg: 'rgba(251, 191, 36, 0.15)', text: '#FBBF24' },
  LLC: { bg: 'rgba(201, 169, 110, 0.15)', text: '#C9A96E' },
  'C-Corp': { bg: 'rgba(248, 113, 113, 0.15)', text: '#F87171' },
};

const statusConfig: Record<string, { dot: string; text: string }> = {
  Active: { dot: '#4ADE80', text: 'Active' },
  Pending: { dot: '#FBBF24', text: 'Pending' },
  Suspended: { dot: '#F87171', text: 'Suspended' },
};

export default function ClientManagement() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const [clients, setClients] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedClient, setSelectedClient] = useState<any>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const loadClients = async () => {
    try {
      const data = await getClients();
      setClients(data);
    } catch (err) {
      console.error('Failed to load clients:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadClients();
  }, []);

  useEffect(() => {
    if (loading) return;
    const ctx = gsap.context(() => {
      gsap.fromTo(
        sectionRef.current,
        { opacity: 0, y: 30 },
        {
          opacity: 1,
          y: 0,
          duration: 0.5,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: sectionRef.current,
            start: 'top 80%',
            toggleActions: 'play none none none',
          },
        }
      );
    }, sectionRef);

    return () => ctx.revert();
  }, [loading]);

  const handleEdit = (client: any) => {
    setSelectedClient(client);
    setModalOpen(true);
  };

  const handleView = (client: any) => {
    setSelectedClient(client);
    setDrawerOpen(true);
  };

  const handleDelete = async (clientId: string) => {
    try {
      await deleteClient(clientId);
      setDeleteConfirm(null);
      loadClients();
    } catch (err) {
      console.error('Failed to delete client:', err);
    }
  };

  const handleAdd = () => {
    setSelectedClient(null);
    setModalOpen(true);
  };

  return (
    <section id="clients" className="bg-canvas px-4 md:px-8 py-8">
      <div ref={sectionRef} className="max-w-[1440px] mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="font-serif text-[32px] text-text-primary">Client Management</h2>
          <button
            onClick={handleAdd}
            className="flex items-center gap-2 font-sans text-sm font-medium border border-gold text-gold bg-transparent px-5 py-2 rounded-md transition-all duration-200 hover:bg-gold-muted"
          >
            <Plus size={16} />
            Add Client
          </button>
        </div>

        {loading ? (
          <div className="text-text-secondary font-sans text-sm">Loading clients...</div>
        ) : clients.length === 0 ? (
          <div className="bg-surface border border-divider rounded-lg p-8 text-center">
            <p className="text-text-secondary font-sans text-sm mb-4">No clients found.</p>
            <button
              onClick={handleAdd}
              className="font-sans text-sm font-medium border border-gold text-gold bg-transparent px-5 py-2 rounded-md transition-all duration-200 hover:bg-gold-muted"
            >
              Add Your First Client
            </button>
          </div>
        ) : (
          <div className="bg-surface border border-divider rounded-lg overflow-hidden overflow-x-auto">
            <table className="w-full min-w-[900px]">
              <thead>
                <tr className="bg-surface">
                  {['Client ID', 'Name', 'Entity Type', 'Accounts Linked', 'Documents Processed', 'Created', 'Status', 'Actions'].map((header) => (
                    <th
                      key={header}
                      className="font-mono text-[11px] uppercase text-text-secondary text-left px-4 py-3"
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {clients.map((client) => {
                  const entity = entityTypeConfig[client.entity_type] || entityTypeConfig['Individual'];
                  const status = statusConfig[client.status] || statusConfig['Active'];
                  return (
                    <tr
                      key={client.id}
                      className="border-t border-divider hover:bg-surface-hover transition-colors duration-150"
                    >
                      <td className="font-mono text-sm text-gold px-4 py-3">{client.id}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Shield size={14} className="text-success flex-shrink-0" />
                          <span className="font-sans text-sm text-text-primary">{client.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className="inline-block font-sans text-xs font-medium px-2.5 py-1 rounded"
                          style={{ backgroundColor: entity.bg, color: entity.text }}
                        >
                          {client.entity_type}
                        </span>
                      </td>
                      <td className="font-sans text-sm text-text-primary px-4 py-3">{client.accounts_linked || 0}</td>
                      <td className="font-sans text-sm text-text-primary px-4 py-3">{(client.documents_processed || 0).toLocaleString()}</td>
                      <td className="font-mono text-xs text-text-secondary px-4 py-3">
                        {client.created_at ? new Date(client.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: status.dot }} />
                          <span className="font-sans text-xs" style={{ color: status.dot }}>{status.text}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleView(client)}
                            className="p-1.5 rounded hover:bg-white/5 transition-colors"
                            aria-label="View client"
                          >
                            <Eye size={14} className="text-text-secondary" />
                          </button>
                          <button
                            onClick={() => handleEdit(client)}
                            className="p-1.5 rounded hover:bg-white/5 transition-colors"
                            aria-label="Edit client"
                          >
                            <Pencil size={14} className="text-text-secondary" />
                          </button>
                          <button
                            onClick={() => setDeleteConfirm(client.id)}
                            className="p-1.5 rounded hover:bg-red-500/10 transition-colors"
                            aria-label="Delete client"
                          >
                            <Trash2 size={14} className="text-red-400" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Delete Confirmation */}
        {deleteConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
            <div className="bg-surface border border-divider rounded-xl p-6 max-w-sm mx-4">
              <p className="text-text-primary font-sans text-sm mb-4">
                Are you sure you want to delete this client? This cannot be undone.
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
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}

        <ClientModal
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          onSuccess={loadClients}
          client={selectedClient}
        />

        <ClientViewDrawer
          isOpen={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          client={selectedClient}
        />
      </div>
    </section>
  );
}
