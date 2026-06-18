import PlaceholderPage from "@/components/PlaceholderPage";
import { BookOpen } from "lucide-react";

export default function JournalEntriesPage() {
  return (
    <PlaceholderPage
      title="Journal Entries"
      description="Create double-entry journal entries with line items, post them to transactions, and manage unposted entries."
      icon={<BookOpen size={32} />}
      endpoints={[
        { method: "GET", path: "/api/journal-entries", description: "List journal entries" },
        { method: "POST", path: "/api/journal-entries", description: "Create a journal entry" },
        { method: "GET", path: "/api/journal-entries/{id}", description: "Get journal entry details" },
        { method: "POST", path: "/api/journal-entries/{id}/post", description: "Post journal entry to transactions" },
        { method: "DELETE", path: "/api/journal-entries/{id}", description: "Delete unposted journal entry" },
      ]}
    />
  );
}
