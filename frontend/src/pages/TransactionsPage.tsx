import PlaceholderPage from "@/components/PlaceholderPage";
import { ArrowLeftRight } from "lucide-react";

export default function TransactionsPage() {
  return (
    <PlaceholderPage
      title="Transactions"
      description="Query, filter, reclassify, and manage transactions. Add notes, flags, and resolve review items."
      icon={<ArrowLeftRight size={32} />}
      endpoints={[
        { method: "GET", path: "/api/transactions", description: "List/query transactions with filters" },
        { method: "PATCH", path: "/api/transactions/{id}", description: "Update transaction fields" },
        { method: "DELETE", path: "/api/transactions/{id}", description: "Soft-delete (archive) a transaction" },
        { method: "GET", path: "/api/transactions/summary", description: "Aggregate summary by category/month" },
        { method: "POST", path: "/api/transactions/{id}/notes", description: "Add a note to a transaction" },
        { method: "POST", path: "/api/transactions/{id}/flags", description: "Flag a transaction for review" },
        { method: "PATCH", path: "/api/transactions/{id}/flags/{flag_id}/resolve", description: "Resolve a flag" },
        { method: "POST", path: "/api/transactions/{id}/reclassify", description: "Reclassify a single transaction" },
        { method: "POST", path: "/api/transactions/bulk-reclassify", description: "Bulk reclassify transactions" },
        { method: "GET", path: "/api/categories", description: "List tax categories" },
      ]}
    />
  );
}
