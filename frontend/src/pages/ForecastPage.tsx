import PlaceholderPage from "@/components/PlaceholderPage";
import { TrendingUp } from "lucide-react";

export default function ForecastPage() {
  return (
    <PlaceholderPage
      title="Forecast"
      description="Project future income and expenses from recurring templates or historical averages."
      icon={<TrendingUp size={32} />}
      endpoints={[
        { method: "GET", path: "/api/forecast", description: "Generate financial forecast" },
      ]}
    />
  );
}
