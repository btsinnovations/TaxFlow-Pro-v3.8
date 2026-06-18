import PlaceholderPage from "@/components/PlaceholderPage";
import { Package } from "lucide-react";

export default function BatchImportPage() {
  return (
    <PlaceholderPage
      title="Batch Import"
      description="Upload ZIP archives of CSV transaction files, monitor background import jobs, and review results."
      icon={<Package size={32} />}
      endpoints={[
        { method: "POST", path: "/api/batch-import", description: "Start batch import job" },
        { method: "GET", path: "/api/batch-import/{id}/status", description: "Job status" },
        { method: "GET", path: "/api/batch-import/jobs", description: "List jobs" },
      ]}
    />
  );
}
