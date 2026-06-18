import PlaceholderPage from "@/components/PlaceholderPage";
import { Settings } from "lucide-react";

export default function SettingsPage() {
  return (
    <PlaceholderPage
      title="Firm Settings"
      description="Manage firm details, upload a logo, and configure recurring-transaction confidence thresholds."
      icon={<Settings size={32} />}
      endpoints={[
        { method: "GET", path: "/api/settings", description: "Get firm settings" },
        { method: "PUT", path: "/api/settings", description: "Update firm settings" },
        { method: "POST", path: "/api/settings/logo/upload", description: "Upload firm logo" },
        { method: "GET", path: "/api/settings/recurring-thresholds", description: "Get confidence thresholds" },
        { method: "PUT", path: "/api/settings/recurring-thresholds", description: "Update thresholds" },
      ]}
    />
  );
}
