import PlaceholderPage from "@/components/PlaceholderPage";
import { Archive } from "lucide-react";

export default function ArchivePage() {
  return (
    <PlaceholderPage
      title="Archive & Restore"
      description="Archive a client's transactions by tax year and restore them later when needed."
      icon={<Archive size={32} />}
      endpoints={[
        { method: "POST", path: "/api/clients/{id}/archive-year", description: "Archive year transactions" },
        { method: "POST", path: "/api/clients/{id}/restore-year", description: "Restore archived transactions" },
      ]}
    />
  );
}
