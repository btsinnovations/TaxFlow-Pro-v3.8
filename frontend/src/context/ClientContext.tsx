import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { getClients } from "@/hooks/useAPI";

export interface Client {
  id: number;
  name: string;
  email?: string;
  tax_id?: string;
  user_id?: number;
  created_at?: string;
}

interface ClientContextType {
  clients: Client[];
  selectedClient: Client | null;
  setSelectedClient: (client: Client | null) => void;
  isLoading: boolean;
  error: string | null;
  refreshClients: () => Promise<void>;
}

const ClientContext = createContext<ClientContextType | undefined>(undefined);

const STORAGE_KEY = "taxflow_selected_client_id";

export function ClientProvider({ children }: { children: ReactNode }) {
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClient, setSelectedClientState] = useState<Client | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const setSelectedClient = useCallback((client: Client | null) => {
    setSelectedClientState(client);
    if (client) {
      localStorage.setItem(STORAGE_KEY, String(client.id));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const refreshClients = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getClients();
      setClients(data);

      // Restore selection from storage if it exists in the loaded list
      const storedId = localStorage.getItem(STORAGE_KEY);
      if (storedId) {
        const id = Number(storedId);
        const match = data.find((c: Client) => c.id === id);
        if (match) {
          setSelectedClientState(match);
        } else if (data.length > 0 && !selectedClient) {
          setSelectedClientState(data[0]);
          localStorage.setItem(STORAGE_KEY, String(data[0].id));
        }
      } else if (data.length > 0 && !selectedClient) {
        setSelectedClientState(data[0]);
        localStorage.setItem(STORAGE_KEY, String(data[0].id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load clients");
    } finally {
      setIsLoading(false);
    }
  }, [selectedClient]);

  useEffect(() => {
    refreshClients();
  }, [refreshClients]);

  return (
    <ClientContext.Provider
      value={{
        clients,
        selectedClient,
        setSelectedClient,
        isLoading,
        error,
        refreshClients,
      }}
    >
      {children}
    </ClientContext.Provider>
  );
}

export function useClient() {
  const context = useContext(ClientContext);
  if (context === undefined) {
    throw new Error("useClient must be used within a ClientProvider");
  }
  return context;
}
