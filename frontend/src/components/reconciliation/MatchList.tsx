import { Button } from "@/components/ui/button";
import { Check, Link2, Unlink } from "lucide-react";

export interface MatchPair {
  match_id: number;
  ledger_tx_id: number | null;
  statement_tx_id: string | null;
  status: string;
  ledger_description?: string;
  ledger_amount?: number;
  statement_description?: string;
  statement_amount?: number;
}

interface MatchListProps {
  matches: MatchPair[];
  onUnmatch: (matchId: number) => void;
  onAccept: (matchId: number) => void;
}

export function MatchList({ matches, onUnmatch, onAccept }: MatchListProps) {
  if (matches.length === 0) {
    return <p className="text-sm text-muted-foreground text-center py-4">No matches found.</p>;
  }

  return (
    <div className="space-y-2">
      {matches.map((m) => (
        <div
          key={m.match_id}
          className="flex items-center justify-between rounded-md border border-divider p-3"
        >
          <div className="flex-1 space-y-1">
            <div className="flex items-center gap-2 text-sm">
              <Link2 className="h-3 w-3 text-green-500" />
              <span className="font-medium">{m.ledger_description ?? `Tx #${m.ledger_tx_id}`}</span>
              <span className="text-muted-foreground">↔</span>
              <span>{m.statement_description ?? `Stmt ${m.statement_tx_id}`}</span>
            </div>
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span>Ledger: ${m.ledger_amount?.toFixed(2) ?? "?"}</span>
              <span>Statement: ${m.statement_amount?.toFixed(2) ?? "?"}</span>
              <span className={`px-2 rounded ${m.status === "matched" ? "bg-green-500/10 text-green-600" : "bg-yellow-500/10 text-yellow-600"}`}>
                {m.status}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {m.status !== "matched" && (
              <Button variant="ghost" size="icon" title="Accept match" onClick={() => onAccept(m.match_id)}>
                <Check className="h-4 w-4 text-green-500" />
              </Button>
            )}
            <Button variant="ghost" size="icon" title="Unmatch" onClick={() => onUnmatch(m.match_id)}>
              <Unlink className="h-4 w-4 text-red-500" />
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}