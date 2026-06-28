import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MatchList } from "@/components/reconciliation/MatchList";

describe("MatchList", () => {
  it("shows empty message when no matches", () => {
    render(<MatchList matches={[]} onUnmatch={() => {}} onAccept={() => {}} />);
    expect(screen.getByText("No matches found.")).toBeInTheDocument();
  });

  it("renders match pairs", () => {
    const matches = [
      {
        match_id: 1,
        ledger_tx_id: 42,
        statement_tx_id: "STMT-001",
        status: "pending",
        ledger_description: "Coffee Shop",
        ledger_amount: 5.0,
        statement_description: "STARBUCKS",
        statement_amount: 5.0,
      },
    ];
    render(<MatchList matches={matches} onUnmatch={() => {}} onAccept={() => {}} />);
    expect(screen.getByText("Coffee Shop")).toBeInTheDocument();
    expect(screen.getByText("STARBUCKS")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
  });
});