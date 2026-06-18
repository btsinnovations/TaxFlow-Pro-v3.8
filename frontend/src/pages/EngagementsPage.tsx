import PlaceholderPage from "@/components/PlaceholderPage";
import { ClipboardList } from "lucide-react";

export default function EngagementsPage() {
  return (
    <PlaceholderPage
      title="Engagements"
      description="Browse engagement templates and create new client engagements from a template."
      icon={<ClipboardList size={32} />}
      endpoints={[
        { method: "GET", path: "/api/engagements/templates", description: "List engagement templates" },
        { method: "GET", path: "/api/engagements/templates/{type}", description: "Get template detail" },
        { method: "POST", path: "/api/engagements/from-template", description: "Create engagement from template" },
      ]}
    />
  );
}
