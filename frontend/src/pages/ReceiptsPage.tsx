import PlaceholderPage from "@/components/PlaceholderPage";
import { ReceiptText } from "lucide-react";

export default function ReceiptsPage() {
  return (
    <PlaceholderPage
      title="Receipts"
      description="Upload receipt images or PDFs, view extracted details, and match receipts to transactions."
      icon={<ReceiptText size={32} />}
      endpoints={[
        { method: "POST", path: "/api/receipts/upload", description: "Upload a receipt" },
        { method: "GET", path: "/api/receipts", description: "List receipts for a client" },
        { method: "GET", path: "/api/receipts/{id}", description: "Get receipt details" },
        { method: "DELETE", path: "/api/receipts/{id}", description: "Delete a receipt" },
        { method: "POST", path: "/api/receipts/{id}/match", description: "Match receipt to candidate transactions" },
      ]}
    />
  );
}
