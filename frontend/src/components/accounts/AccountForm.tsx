import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export interface AccountFormData {
  code: string;
  name: string;
  type: string;
  parent_id?: string;
  description?: string;
}

interface AccountFormProps {
  open: boolean;
  initialData?: Partial<AccountFormData>;
  onSubmit: (data: AccountFormData) => void;
  onClose: () => void;
}

const ACCOUNT_TYPES = ["asset", "liability", "equity", "income", "expense"];

export function AccountForm({ open, initialData, onSubmit, onClose }: AccountFormProps) {
  const [code, setCode] = useState(initialData?.code ?? "");
  const [name, setName] = useState(initialData?.name ?? "");
  const [type, setType] = useState(initialData?.type ?? "asset");
  const [parentId, setParentId] = useState(initialData?.parent_id ?? "");
  const [description, setDescription] = useState(initialData?.description ?? "");

  const handleSubmit = () => {
    onSubmit({ code, name, type, parent_id: parentId || undefined, description: description || undefined });
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{initialData ? "Edit Account" : "Add Account"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="code">Account Code</Label>
            <Input id="code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. 1010" />
          </div>
          <div>
            <Label htmlFor="name">Account Name</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Cash - Checking" />
          </div>
          <div>
            <Label>Account Type</Label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ACCOUNT_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="parent">Parent Account ID (optional)</Label>
            <Input id="parent" value={parentId} onChange={(e) => setParentId(e.target.value)} placeholder="Parent account code" />
          </div>
          <div>
            <Label htmlFor="desc">Description (optional)</Label>
            <Input id="desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Notes" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={!code || !name}>Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}