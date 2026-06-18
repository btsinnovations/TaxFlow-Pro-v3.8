import PlaceholderPage from "@/components/PlaceholderPage";
import { Building } from "lucide-react";

export default function BankConnectionsPage() {
  return (
    <PlaceholderPage
      title="Bank Connections"
      description="Create OFX connections to financial institutions, list connections, and fetch transactions."
      icon={<Building size={32} />}
      endpoints={[
        { method: "GET", path: "/api/bank-connections", description: "List bank connections" },
        { method: "POST", path: "/api/bank-connections", description: "Create OFX connection" },
        { method: "POST", path: "/api/bank-connections/{id}/fetch", description: "Fetch transactions via OFX" },
        { method: "DELETE", path: "/api/bank-connections/{id}", description: "Delete connection" },
      ]}
    />
  );
}
