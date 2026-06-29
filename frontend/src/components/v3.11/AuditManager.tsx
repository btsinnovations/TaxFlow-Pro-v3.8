import { useEffect, useState } from "react";
import ModuleShell from "./ModuleShell";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { getAuditLog, verifyAuditChain } from "@/hooks/useAPIExtensions";
import { ShieldCheck, Loader2, AlertTriangle } from "lucide-react";

export default function AuditManager() {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<string | null>(null);

  useEffect(() => {
    getAuditLog(100)
      .then((data) => setEntries(Array.isArray(data) ? data : data?.entries ?? []))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleVerify() {
    setVerifying(true);
    setVerifyResult(null);
    try {
      const res = await verifyAuditChain();
      setVerifyResult(res?.valid ? "Chain valid ✓" : res?.message || JSON.stringify(res));
    } catch (e: any) {
      setVerifyResult(`Error: ${e.message}`);
    } finally {
      setVerifying(false);
    }
  }

  return (
    <ModuleShell title="Audit Log" description="View system audit events and verify the audit chain." moduleId="M01">
      <div className="flex items-center justify-between mb-4">
        <p className="text-text-secondary text-sm">{entries.length} entries</p>
        <Button onClick={handleVerify} disabled={verifying} className="bg-gold text-black hover:bg-gold/90">
          {verifying ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <ShieldCheck className="w-4 h-4 mr-1" />}
          Verify Chain
        </Button>
      </div>

      {verifyResult && (
        <div className="mb-4 rounded-md border border-gold/30 bg-gold/5 p-3 text-sm text-text-primary">
          {verifyResult}
        </div>
      )}

      {loading && <div className="flex items-center gap-2 text-text-secondary"><Loader2 className="w-4 h-4 animate-spin" /> Loading...</div>}
      {error && <div className="flex items-center gap-2 text-red-400"><AlertTriangle className="w-4 h-4" /> {error}</div>}

      {!loading && !error && (
        <div className="rounded-md border border-divider overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="border-divider hover:bg-transparent">
                <TableHead className="text-text-secondary">ID</TableHead>
                <TableHead className="text-text-secondary">Actor</TableHead>
                <TableHead className="text-text-secondary">Action</TableHead>
                <TableHead className="text-text-secondary">Resource</TableHead>
                <TableHead className="text-text-secondary">Timestamp</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-text-secondary py-8">No audit entries found.</TableCell>
                </TableRow>
              ) : (
                entries.map((e: any) => (
                  <TableRow key={e.id} className="border-divider">
                    <TableCell className="text-text-primary">{e.id}</TableCell>
                    <TableCell className="text-text-primary">{e.actor_id ?? "system"}</TableCell>
                    <TableCell className="text-text-primary">{e.action}</TableCell>
                    <TableCell className="text-text-primary">{e.resource_type ?? e.resource ?? "—"}</TableCell>
                    <TableCell className="text-text-secondary">{e.timestamp ?? e.created_at ?? "—"}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </ModuleShell>
  );
}