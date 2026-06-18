import PlaceholderPage from "@/components/PlaceholderPage";
import { Calculator } from "lucide-react";

export default function DepreciationPage() {
  return (
    <PlaceholderPage
      title="Depreciation"
      description="Calculate depreciation schedules using MACRS, straight-line, Section 179, and bonus depreciation methods."
      icon={<Calculator size={32} />}
      endpoints={[
        { method: "GET", path: "/api/depreciation/methods", description: "List depreciation methods" },
        { method: "GET", path: "/api/depreciation/macrs-tables", description: "IRS MACRS tables" },
        { method: "POST", path: "/api/depreciation/calculate", description: "Calculate depreciation schedule" },
      ]}
    />
  );
}
