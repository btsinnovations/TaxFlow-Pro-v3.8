export interface RegisterRow {
  id: number;
  date: string;
  description: string;
  amount: number;
  tx_type: "debit" | "credit" | "deposit" | "withdrawal" | string;
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
  reconciled?: boolean;
}

export interface SplitLine {
  id?: number;
  coa_account_id: number;
  amount: number;
  description?: string;
}

export interface RegisterFilters {
  accountId?: number;
  startDate?: string;
  endDate?: string;
  search?: string;
  coaAccountId?: number;
}

export type TransactionType = "debit" | "credit" | "deposit" | "withdrawal";

export const TRANSACTION_TYPES: TransactionType[] = ["debit", "credit", "deposit", "withdrawal"];