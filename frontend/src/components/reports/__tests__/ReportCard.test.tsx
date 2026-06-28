import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReportCard } from "@/components/reports/ReportCard";

describe("ReportCard", () => {
  it("shows empty message when no data", () => {
    render(<ReportCard title="P&L" data={[]} />);
    expect(screen.getByText("No data. Run the report to see results.")).toBeInTheDocument();
  });

  it("renders data when provided", () => {
    render(<ReportCard title="Trial Balance" data={{ debit: 1000, credit: 1000 }} />);
    expect(screen.getByText("Trial Balance")).toBeInTheDocument();
    expect(screen.getByText(/"debit": 1000/)).toBeInTheDocument();
  });

  it("shows export button when data present and onExport provided", () => {
    render(<ReportCard title="Cash Flow" data={[{ month: 1 }]} onExport={() => {}} />);
    expect(screen.getByText("Export")).toBeInTheDocument();
  });
});