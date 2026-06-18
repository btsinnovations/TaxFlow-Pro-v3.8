import PlaceholderPage from "@/components/PlaceholderPage";
import { CalendarClock } from "lucide-react";

export default function PeriodsPage() {
  return (
    <PlaceholderPage
      title="Accounting Periods"
      description="Define accounting periods for each client, lock closed periods, and check whether a date falls in a locked range."
      icon={<CalendarClock size={32} />}
      endpoints={[
        { method: "GET", path: "/api/periods", description: "List accounting periods" },
        { method: "POST", path: "/api/periods", description: "Create an accounting period" },
        { method: "POST", path: "/api/periods/{id}/lock", description: "Lock a period" },
        { method: "POST", path: "/api/periods/{id}/unlock", description: "Unlock a period" },
        { method: "GET", path: "/api/periods/check", description: "Check if a date is locked" },
      ]}
    />
  );
}
