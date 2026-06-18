import PlaceholderPage from "@/components/PlaceholderPage";
import { FileSignature } from "lucide-react";

export default function ReportsPage() {
  return (
    <PlaceholderPage
      title="Signed Reports"
      description="Generate tamper-evident signed reports such as P&L, balance sheet, cash flow, tax summary, and trial balance."
      icon={<FileSignature size={32} />}
      endpoints={[
        { method: "POST", path: "/api/reports/{type}/sign", description: "Sign a report with HMAC-SHA256" },
        { method: "GET", path: "/api/reports/signed", description: "List signed reports" },
        { method: "GET", path: "/api/reports/signed/{id}", description: "Get signed report details" },
      ]}
    />
  );
}
