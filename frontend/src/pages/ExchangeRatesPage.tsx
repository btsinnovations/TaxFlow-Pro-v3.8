import PlaceholderPage from "@/components/PlaceholderPage";
import { Coins } from "lucide-react";

export default function ExchangeRatesPage() {
  return (
    <PlaceholderPage
      title="Exchange Rates"
      description="Maintain currency exchange rates, bulk import conversions, and convert amounts between currencies."
      icon={<Coins size={32} />}
      endpoints={[
        { method: "GET", path: "/api/exchange-rates", description: "List exchange rates" },
        { method: "POST", path: "/api/exchange-rates", description: "Create/update rate" },
        { method: "POST", path: "/api/exchange-rates/import", description: "Bulk import rates" },
        { method: "GET", path: "/api/exchange-rates/convert", description: "Convert currency" },
      ]}
    />
  );
}
