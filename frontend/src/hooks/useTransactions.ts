import { useEffect, useState, useCallback } from "react";
import { fetchWithAuth } from "@/hooks/useAPI";

export interface Transaction {
  id: number;
  date: string;
  description: string;
  amount: number;
  tx_type: string;
  category?: string | null;
  running_balance?: number | null;
  coa_account_id?: number | null;
  gl_account_id?: number | null;
  workpaper_ref?: string | null;
  txn_uid?: string | null;
  import_source?: string | null;
  foreign_amount?: number | null;
  foreign_currency?: string | null;
  fx_rate_snapshot?: number | null;
  statement_id?: number | null;
  tenant_id?: number | null;
}

export interface UseTransactionsOptions {
  accountId?: number;
  startDate?: string;
  endDate?: string;
  limit?: number;
}

export function useTransactions(options: UseTransactionsOptions = {}) {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (options.accountId) params.set("account_id", String(options.accountId));
      if (options.startDate) params.set("start_date", options.startDate);
      if (options.endDate) params.set("end_date", options.endDate);
      if (options.limit) params.set("limit", String(options.limit));

      const res = await fetchWithAuth(`/api/transactions?${params.toString()}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setTransactions(Array.isArray(data) ? data : data.transactions ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load transactions");
    } finally {
      setLoading(false);
    }
  }, [options.accountId, options.startDate, options.endDate, options.limit]);

  useEffect(() => {
    load();
  }, [load]);

  const updateTransaction = useCallback(
    async (id: number, patch: Partial<Transaction>) => {
      try {
        const res = await fetchWithAuth(`/api/transactions/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        });
        if (!res.ok) throw new Error(await res.text());
        const updated = await res.json();
        setTransactions((prev) =>
          prev.map((t) => (t.id === id ? { ...t, ...updated } : t)),
        );
        return updated;
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to update transaction");
        throw e;
      }
    },
    [],
  );

  const deleteTransaction = useCallback(async (id: number) => {
    try {
      const res = await fetchWithAuth(`/api/transactions/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(await res.text());
      setTransactions((prev) => prev.filter((t) => t.id !== id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete transaction");
      throw e;
    }
  }, []);

  return {
    transactions,
    loading,
    error,
    reload: load,
    updateTransaction,
    deleteTransaction,
  };
}