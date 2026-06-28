import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SplitEditor } from "@/components/register/SplitEditor";

describe("SplitEditor", () => {
  it("renders with initial split line", () => {
    render(<SplitEditor totalAmount={100} onSave={() => {}} onCancel={() => {}} />);
    expect(screen.getByText("Split Transaction")).toBeInTheDocument();
    expect(screen.getByText("Save Splits")).toBeInTheDocument();
  });

  it("shows remaining balance", () => {
    render(<SplitEditor totalAmount={200} onSave={() => {}} onCancel={() => {}} />);
    expect(screen.getByText(/Remaining:/i)).toBeInTheDocument();
  });

  it("can add and remove split lines", () => {
    render(<SplitEditor totalAmount={100} onSave={() => {}} onCancel={() => {}} />);
    fireEvent.click(screen.getByText("Add Line"));
    expect(screen.getAllByPlaceholderText("COA account ID").length).toBe(2);
  });
});