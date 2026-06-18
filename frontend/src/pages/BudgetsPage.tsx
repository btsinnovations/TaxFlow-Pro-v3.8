import PlaceholderPage from "@/components/PlaceholderPage";
import { PiggyBank } from "lucide-react";

export default function BudgetsPage() {
  return (
    <PlaceholderPage
      title="Budgets"
      description="Create client budgets by category, track spending, and compare budget vs actual."
      icon={<PiggyBank size={32} />}
      endpoints={[
        { method: "GET", path: "/api/budgets", description: "List budgets for a client" },
        { method: "POST", path: "/api/budgets", description: "Create a budget with entries" },
        { method: "GET", path: "/api/budgets/{id}", description: "Get budget with entries" },
        { method: "PUT", path: "/api/budgets/{id}", description: "Update a budget" },
        { method: "DELETE", path: "/api/budgets/{id}", description: "Delete a budget" },
        { method: "GET", path: "/api/budgets/{id}/vs-actual", description: "Budget vs actual report" },
      ]}
    />
  );
}
