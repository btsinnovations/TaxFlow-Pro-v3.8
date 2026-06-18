import PlaceholderPage from "@/components/PlaceholderPage";
import { Receipt } from "lucide-react";

export default function TaxSummaryPage() {
  return (
    <PlaceholderPage
      title="Tax Summary"
      description="View annual income, expenses, and net totals for a selected client and tax year."
      icon={<Receipt size={32} />}
      endpoints={[
        { method: "GET", path: "/api/tax/summary/{year}", description: "Yearly income, expense, and net summary" },
      ]}
    />
  );
}
