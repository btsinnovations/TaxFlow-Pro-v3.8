import { ChevronDown, Building2, RefreshCw } from "lucide-react";
import { useClient } from "@/context/ClientContext";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";

export default function ClientSelector() {
  const { clients, selectedClient, setSelectedClient, isLoading, refreshClients } = useClient();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-divider bg-surface hover:border-gold/50 transition-colors text-sm text-text-primary">
          <Building2 size={14} className="text-gold" />
          <span className="max-w-[160px] truncate">
            {isLoading ? "Loading clients..." : selectedClient ? selectedClient.name : "Select client"}
          </span>
          <ChevronDown size={14} className="text-text-secondary" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="bg-surface border-divider text-text-primary min-w-[220px]">
        {clients.length === 0 && !isLoading && (
          <DropdownMenuItem disabled className="text-text-secondary">
            No clients available
          </DropdownMenuItem>
        )}
        {clients.map((client) => (
          <DropdownMenuItem
            key={client.id}
            onClick={() => setSelectedClient(client)}
            className={`cursor-pointer hover:bg-surface-hover focus:bg-surface-hover ${
              selectedClient?.id === client.id ? "text-gold" : ""
            }`}
          >
            <div className="flex flex-col">
              <span className="font-medium">{client.name}</span>
              {client.tax_id && (
                <span className="text-[10px] text-text-secondary font-mono">{client.tax_id}</span>
              )}
            </div>
          </DropdownMenuItem>
        ))}
        <DropdownMenuItem
          onClick={() => refreshClients()}
          className="cursor-pointer hover:bg-surface-hover focus:bg-surface-hover border-t border-divider mt-1"
        >
          <RefreshCw size={12} className="mr-2 text-gold" />
          Refresh clients
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
