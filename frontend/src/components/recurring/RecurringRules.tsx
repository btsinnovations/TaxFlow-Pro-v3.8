import { useEffect, useState } from "react";
import ModuleShell from "@/components/v3.11/ModuleShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/hooks/useToast";
import { Repeat, Play } from "lucide-react";

interface RecurringRule {
  id: number;
  account_id: number;
  description: string;
  amount: number;
  frequency: string;
  start_date: string;
  end_date: string | null;
  count: number | null;
  next_date: string | null;
  is_active: boolean;
}

export default function RecurringRules() {
  const [rules, setRules] = useState<RecurringRule[]>([]);
  const [loading, setLoading] = useState(false);
  const { addToast } = useToast();

  const fetchRules = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/recurring", { credentials: "include" });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setRules(data);
    } catch (err) {
      addToast(`Failed to load rules: ${err instanceof Error ? err.message : String(err)}`, "error");
    } finally {
      setLoading(false);
    }
  };

  const materialize = async (id: number) => {
    try {
      const res = await fetch(`/api/recurring/${id}/materialize`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      addToast(`Materialized ${data.materialized} transaction(s)`, "success");
      fetchRules();
    } catch (err) {
      addToast(`Materialize failed: ${err instanceof Error ? err.message : String(err)}`, "error");
    }
  };

  useEffect(() => {
    fetchRules();
  }, []);

  return (
    <ModuleShell
      title="Recurring Rules"
      description="Manage scheduled transactions and generate real entries from recurring rules."
      moduleId="3.11.04"
    >
      <Card className="bg-canvas border-divider">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-text-primary flex items-center gap-2">
              <Repeat className="w-5 h-5 text-gold" />
              Recurring Rules
            </CardTitle>
            <CardDescription className="text-text-secondary">
              Grid view of scheduled rules. Click Materialize to create real transactions.
            </CardDescription>
          </div>
          <Button
            size="sm"
            className="bg-gold text-canvas hover:bg-gold/90"
            onClick={fetchRules}
            disabled={loading}
          >
            Refresh
          </Button>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border border-divider overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent border-divider">
                  <TableHead className="text-text-secondary">Description</TableHead>
                  <TableHead className="text-text-secondary">Frequency</TableHead>
                  <TableHead className="text-text-secondary">Amount</TableHead>
                  <TableHead className="text-text-secondary">Start</TableHead>
                  <TableHead className="text-text-secondary">Next Date</TableHead>
                  <TableHead className="text-text-secondary">Active</TableHead>
                  <TableHead className="text-text-secondary text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-text-secondary py-8">
                      {loading ? "Loading..." : "No recurring rules found."}
                    </TableCell>
                  </TableRow>
                ) : (
                  rules.map((rule) => (
                    <TableRow key={rule.id} className="border-divider hover:bg-white/5">
                      <TableCell className="text-text-primary font-medium">
                        {rule.description}
                      </TableCell>
                      <TableCell className="text-text-secondary capitalize">{rule.frequency}</TableCell>
                      <TableCell className="text-text-secondary">
                        {rule.amount.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-text-secondary">{rule.start_date}</TableCell>
                      <TableCell className="text-text-secondary">{rule.next_date ?? "—"}</TableCell>
                      <TableCell className="text-text-secondary">
                        {rule.is_active ? "Yes" : "No"}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-gold/30 text-gold hover:bg-gold/10"
                          onClick={() => materialize(rule.id)}
                          disabled={!rule.is_active}
                        >
                          <Play className="w-4 h-4 mr-1" />
                          Materialize
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </ModuleShell>
  );
}
