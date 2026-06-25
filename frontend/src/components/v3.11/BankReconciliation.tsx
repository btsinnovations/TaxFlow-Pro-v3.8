import ModuleShell from "./ModuleShell";

export default function BankReconciliation() {
  return (
    <ModuleShell
      title="Bank Reconciliation"
      description="Match imported bank statement transactions against ledger transactions and mark cleared items."
      moduleId="3.11.09"
    />
  );
}
