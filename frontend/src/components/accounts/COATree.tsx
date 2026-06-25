import { useEffect, useState } from "react";
import ModuleShell from "@/components/v3.11/ModuleShell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchWithAuth } from "@/hooks/useAPI";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

interface COAAccount {
  id: number;
  number: string;
  name: string;
  type: string;
  balance: number | null;
  children?: COAAccount[];
}

const accountTypes = ["asset", "liability", "equity", "income", "expense"];

export default function COATree() {
  const [accounts, setAccounts] = useState<COAAccount[]>([]);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState("expense");
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`${API_BASE}/coa`);
      const data = await res.json();
      setAccounts(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("Failed to load COA", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    await fetchWithAuth(`${API_BASE}/coa`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ number: code, name, type }),
    });
    setCode("");
    setName("");
    load();
  };

  return (
    <ModuleShell
      title="Chart of Accounts"
      description="v3.11.01 — Manage your five-class bookkeeping chart of accounts."
      moduleId="3.11.01"
    >
      <Card className="bg-canvas border-divider mb-6">
        <CardHeader>
          <CardTitle className="text-text-primary">Add Account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="space-y-2">
              <Label>Code</Label>
              <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="6100" />
            </div>
            <div className="space-y-2">
              <Label>Name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Office Supplies" />
            </div>
            <div className="space-y-2">
              <Label>Type</Label>
              <Select value={type} onValueChange={setType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {accountTypes.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end">
              <Button onClick={create} disabled={!code || !name || loading}>
                Add Account
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-canvas border-divider">
        <CardHeader>
          <CardTitle className="text-text-primary">Accounts</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="border rounded-md overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  <th className="px-4 py-2 text-left">Code</th>
                  <th className="px-4 py-2 text-left">Name</th>
                  <th className="px-4 py-2 text-left">Type</th>
                  <th className="px-4 py-2 text-right">Balance</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((a) => (
                  <tr key={a.id} className="border-t">
                    <td className="px-4 py-2">{a.number}</td>
                    <td className="px-4 py-2">{a.name}</td>
                    <td className="px-4 py-2 capitalize">{a.type}</td>
                    <td className="px-4 py-2 text-right">
                      {a.balance !== null && a.balance !== undefined
                        ? a.balance.toLocaleString("en-US", {
                            style: "currency",
                            currency: "USD",
                          })
                        : "—"}
                    </td>
                  </tr>
                ))}
                {accounts.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-text-secondary">
                      No accounts yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </ModuleShell>
  );
}
