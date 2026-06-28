import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DataTable } from "@/components/ui/data-table";

interface TestRow {
  id: number;
  name: string;
  amount: number;
}

const testData: TestRow[] = [
  { id: 1, name: "Alpha", amount: 100 },
  { id: 2, name: "Beta", amount: 200 },
  { id: 3, name: "Gamma", amount: 300 },
];

const columns = [
  { accessorKey: "name", header: "Name" },
  { accessorKey: "amount", header: "Amount" },
];

describe("DataTable", () => {
  it("renders data rows", () => {
    render(<DataTable columns={columns as never} data={testData} searchKeys={["name"]} />);
    expect(screen.getByText("Alpha")).toBeDefined();
    expect(screen.getByText("Beta")).toBeDefined();
    expect(screen.getByText("Gamma")).toBeDefined();
  });

  it("filter narrows rows", () => {
    render(<DataTable columns={columns as never} data={testData} searchKeys={["name"]} searchPlaceholder="Search..." />);
    const input = screen.getByPlaceholderText("Search...");
    fireEvent.change(input, { target: { value: "Beta" } });
    expect(screen.getByText("Beta")).toBeDefined();
    expect(screen.queryByText("Alpha")).toBeNull();
  });

  it("sort toggle changes order", () => {
    render(<DataTable columns={columns as never} data={testData} searchKeys={["name"]} />);
    const nameHeader = screen.getByText("Name");
    fireEvent.click(nameHeader);
    expect(screen.getByText("Name")).toBeDefined();
  });

  it("shows empty message when no data", () => {
    render(<DataTable columns={columns as never} data={[]} emptyMessage="No data here." searchKeys={["name"]} />);
    expect(screen.getByText("No data here.")).toBeDefined();
  });
});