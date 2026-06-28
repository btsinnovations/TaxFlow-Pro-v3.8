import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, Trash2 } from "lucide-react";

export interface SplitLine {
  coa_account_id: string;
  amount: string;
  description: string;
}

interface SplitEditorProps {
  totalAmount: number;
  onSave: (splits: SplitLine[]) => void;
  onCancel: () => void;
}

export function SplitEditor({ totalAmount, onSave, onCancel }: SplitEditorProps) {
  const [splits, setSplits] = useState<SplitLine[]>([
    { coa_account_id: "", amount: String(totalAmount), description: "" },
  ]);

  const remaining = totalAmount - splits.reduce((sum, s) => sum + (parseFloat(s.amount) || 0), 0);

  const addSplit = () =>
    setSplits([...splits, { coa_account_id: "", amount: "", description: "" }]);

  const removeSplit = (idx: number) =>
    setSplits(splits.filter((_, i) => i !== idx));

  const updateSplit = (idx: number, field: keyof SplitLine, value: string) =>
    setSplits(splits.map((s, i) => (i === idx ? { ...s, [field]: value } : s)));

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-medium">Split Transaction</Label>
        <Button variant="outline" size="sm" onClick={addSplit}>
          <Plus className="h-3 w-3 mr-1" /> Add Line
        </Button>
      </div>
      {splits.map((split, idx) => (
        <div key={idx} className="flex items-end gap-2">
          <div className="flex-1">
            <Label className="text-xs text-muted-foreground">Account ID</Label>
            <Input
              value={split.coa_account_id}
              onChange={(e) => updateSplit(idx, "coa_account_id", e.target.value)}
              placeholder="COA account ID"
              className="text-sm"
            />
          </div>
          <div className="w-28">
            <Label className="text-xs text-muted-foreground">Amount</Label>
            <Input
              type="number"
              value={split.amount}
              onChange={(e) => updateSplit(idx, "amount", e.target.value)}
              className="text-sm"
            />
          </div>
          <div className="flex-1">
            <Label className="text-xs text-muted-foreground">Description</Label>
            <Input
              value={split.description}
              onChange={(e) => updateSplit(idx, "description", e.target.value)}
              placeholder="Optional memo"
              className="text-sm"
            />
          </div>
          <Button variant="ghost" size="icon" onClick={() => removeSplit(idx)}>
            <Trash2 className="h-4 w-4 text-red-500" />
          </Button>
        </div>
      ))}
      <div className="flex items-center justify-between pt-2 border-t">
        <span className={`text-sm ${Math.abs(remaining) < 0.01 ? "text-green-600" : "text-red-600"}`}>
          Remaining: ${remaining.toFixed(2)}
        </span>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button onClick={() => onSave(splits)} disabled={Math.abs(remaining) > 0.01}>
            Save Splits
          </Button>
        </div>
      </div>
    </div>
  );
}