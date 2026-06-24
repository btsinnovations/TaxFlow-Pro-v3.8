// Dev-only fallback data. Production sections should fetch from useAPI hooks.
// Client Management Data
export interface Client {
  id: string;
  name: string;
  entityType: 'Individual' | 'S-Corp' | 'Partnership' | 'LLC' | 'C-Corp';
  accountsLinked: number;
  documentsProcessed: number;
  lastActivity: string;
  status: 'Active' | 'Pending' | 'Suspended';
}

export const clients: Client[] = [
  { id: 'CLT-001847', name: 'Sarah Chen', entityType: 'S-Corp', accountsLinked: 4, documentsProcessed: 1247, lastActivity: '2026-01-15 14:32:09', status: 'Active' },
  { id: 'CLT-001848', name: 'Marcus Johnson', entityType: 'Partnership', accountsLinked: 3, documentsProcessed: 892, lastActivity: '2026-01-15 12:18:33', status: 'Active' },
  { id: 'CLT-001849', name: 'Elena Rodriguez', entityType: 'LLC', accountsLinked: 2, documentsProcessed: 634, lastActivity: '2026-01-14 18:45:22', status: 'Active' },
  { id: 'CLT-001850', name: 'David Park', entityType: 'Individual', accountsLinked: 5, documentsProcessed: 2156, lastActivity: '2026-01-15 09:12:47', status: 'Active' },
  { id: 'CLT-001851', name: 'Apex Consulting LLC', entityType: 'LLC', accountsLinked: 3, documentsProcessed: 1567, lastActivity: '2026-01-14 16:30:11', status: 'Active' },
  { id: 'CLT-001852', name: 'Thomas Wright', entityType: 'C-Corp', accountsLinked: 2, documentsProcessed: 445, lastActivity: '2026-01-13 11:22:08', status: 'Pending' },
  { id: 'CLT-001853', name: 'Rivera & Associates', entityType: 'Partnership', accountsLinked: 4, documentsProcessed: 1834, lastActivity: '2026-01-15 08:55:19', status: 'Active' },
  { id: 'CLT-001854', name: 'Jennifer Kim', entityType: 'S-Corp', accountsLinked: 3, documentsProcessed: 978, lastActivity: '2026-01-14 20:18:42', status: 'Active' },
  { id: 'CLT-001855', name: 'Global Ventures Inc', entityType: 'C-Corp', accountsLinked: 6, documentsProcessed: 3241, lastActivity: '2026-01-15 13:05:37', status: 'Suspended' },
];

// Tax Rules Data
export interface TaxRule {
  id: string;
  name: string;
  category: string;
  description: string;
  appliesTo: string[];
  effectiveDate: string;
  threshold?: string;
  maximum?: string;
  overrideAllowed: boolean;
  autoApply: boolean;
}

export const taxRules: TaxRule[] = [
  { id: 'TAX-RULE-001', name: 'Home Office Deduction', category: 'Deductions', description: '2026: $5/sq ft, max 300 sq ft', appliesTo: ['S-Corp', 'Partnership'], effectiveDate: '2026-01-01', threshold: '$5.00 per square foot', maximum: '$1,500.00', overrideAllowed: true, autoApply: true },
  { id: 'TAX-RULE-002', name: 'Standard Mileage Rate', category: 'Deductions', description: '2026: $0.67/mile for business travel', appliesTo: ['Individual', 'S-Corp', 'Partnership', 'LLC', 'C-Corp'], effectiveDate: '2026-01-01', threshold: '$0.67 per mile', overrideAllowed: true, autoApply: true },
  { id: 'TAX-RULE-003', name: 'Section 179 Depreciation', category: 'Depreciation', description: 'Maximum $1,250,000 immediate expensing', appliesTo: ['S-Corp', 'C-Corp', 'LLC'], effectiveDate: '2026-01-01', threshold: '$1,250,000.00', overrideAllowed: false, autoApply: true },
  { id: 'TAX-RULE-004', name: 'Self-Employment Tax Deduction', category: 'Deductions', description: '50% of SE tax deductible', appliesTo: ['Partnership', 'LLC'], effectiveDate: '2026-01-01', threshold: '50% of calculated SE tax', overrideAllowed: true, autoApply: true },
  { id: 'TAX-RULE-005', name: 'Qualified Business Income', category: 'Deductions', description: '20% deduction on QBI', appliesTo: ['S-Corp', 'Partnership', 'LLC'], effectiveDate: '2026-01-01', threshold: '20% of qualified income', maximum: 'Subject to phase-out', overrideAllowed: false, autoApply: true },
  { id: 'TAX-RULE-006', name: 'Health Insurance Deduction', category: 'Deductions', description: '100% for S-Corp >2% shareholders', appliesTo: ['S-Corp'], effectiveDate: '2026-01-01', threshold: '100% of premiums', overrideAllowed: true, autoApply: true },
  { id: 'TAX-RULE-007', name: 'Employer Retirement Match', category: 'Deductions', description: 'Up to 25% of employee compensation', appliesTo: ['S-Corp', 'C-Corp', 'LLC'], effectiveDate: '2026-01-01', threshold: '25% of W-2 wages', maximum: '$69,000 per employee', overrideAllowed: false, autoApply: true },
  { id: 'TAX-RULE-008', name: 'Research & Development Credit', category: 'Credits', description: '20% of qualified research expenses', appliesTo: ['C-Corp', 'S-Corp'], effectiveDate: '2026-01-01', threshold: '20% of R&D spend', overrideAllowed: false, autoApply: false },
];

// Audit Log Data
export interface AuditEvent {
  timestamp: string;
  severity: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  eventType: 'PROCESS' | 'RULE_CHANGE' | 'USER_ACTION' | 'SYSTEM' | 'EXPORT';
  clientId: string;
  description: string;
  user: string;
  sessionId: string;
}

export const auditEvents: AuditEvent[] = [
  { timestamp: '2026-01-15 14:32:09', severity: 'INFO', eventType: 'PROCESS', clientId: 'CLT-001847', description: 'Wells Fargo statement processed — 247 transactions categorized', user: 'system', sessionId: 'sess-a7f3d2' },
  { timestamp: '2026-01-15 14:28:17', severity: 'INFO', eventType: 'RULE_CHANGE', clientId: '—', description: 'Tax rule updated — Home Office Deduction threshold changed', user: 'admin@taxflow.io', sessionId: 'sess-b2e9c1' },
  { timestamp: '2026-01-15 14:15:33', severity: 'WARNING', eventType: 'PROCESS', clientId: 'CLT-001847', description: 'Chime account flagged for review — purchase sign mismatch on 3 transactions', user: 'system', sessionId: 'sess-a7f3d2' },
  { timestamp: '2026-01-15 13:58:42', severity: 'INFO', eventType: 'SYSTEM', clientId: '—', description: 'ML model retrained — confidence improved 1.8%', user: 'system', sessionId: 'sess-c4d8e3' },
  { timestamp: '2026-01-15 13:45:11', severity: 'INFO', eventType: 'EXPORT', clientId: 'CLT-001847', description: 'QIF export completed — 247 transactions to HomeBank format', user: 'system', sessionId: 'sess-a7f3d2' },
  { timestamp: '2026-01-15 13:22:08', severity: 'INFO', eventType: 'PROCESS', clientId: 'CLT-001848', description: 'Cash App statement ingested — 156 transactions extracted', user: 'system', sessionId: 'sess-d5e7f4' },
  { timestamp: '2026-01-15 12:48:55', severity: 'ERROR', eventType: 'PROCESS', clientId: 'CLT-001855', description: 'TD Bank PDF parse failed — corrupted encryption header', user: 'system', sessionId: 'sess-e6f8g5' },
  { timestamp: '2026-01-15 12:18:33', severity: 'INFO', eventType: 'USER_ACTION', clientId: 'CLT-001848', description: 'Category override applied — "Software" reclassified to "Development Tools"', user: 'cpark@taxflow.io', sessionId: 'sess-f7g9h6' },
  { timestamp: '2026-01-15 11:55:19', severity: 'WARNING', eventType: 'SYSTEM', clientId: '—', description: 'High memory usage detected — pipeline throttled', user: 'system', sessionId: 'sess-g8h0i7' },
  { timestamp: '2026-01-15 11:32:47', severity: 'INFO', eventType: 'EXPORT', clientId: 'CLT-001853', description: 'Excel multi-sheet export completed — summary + transactions + schedule C', user: 'system', sessionId: 'sess-h9i1j8' },
  { timestamp: '2026-01-15 11:15:22', severity: 'INFO', eventType: 'PROCESS', clientId: 'CLT-001850', description: 'Multi-account reconciliation completed — 3 accounts balanced', user: 'system', sessionId: 'sess-i0j2k9' },
  { timestamp: '2026-01-15 10:48:09', severity: 'CRITICAL', eventType: 'SYSTEM', clientId: '—', description: 'Client isolation breach attempt blocked — unauthorized cross-client query', user: 'security', sessionId: 'sess-j1k3l0' },
];

// Pipeline Data
export interface PipelineStage {
  name: string;
  status: 'Active' | 'Idle' | 'Warning' | 'Error';
  throughput: string;
}

export const pipelineStages: PipelineStage[] = [
  { name: 'PDF Ingestion', status: 'Active', throughput: '47 docs/hr' },
  { name: 'OCR Extraction', status: 'Active', throughput: '44 docs/hr' },
  { name: 'Transaction Parsing', status: 'Active', throughput: '1,247 txns/hr' },
  { name: 'ML Categorization', status: 'Active', throughput: '1,198 txns/hr' },
  { name: 'Tax Rule Engine', status: 'Active', throughput: '1,243 txns/hr' },
  { name: 'Export Generation', status: 'Idle', throughput: '—' },
];

// Recent Activity Data
export interface ActivityEvent {
  timestamp: string;
  description: string;
}

export const recentActivity: ActivityEvent[] = [
  { timestamp: '2026-01-15 14:32:09', description: 'Wells Fargo statement processed — 247 transactions categorized' },
  { timestamp: '2026-01-15 14:28:17', description: 'Tax rule updated — Home Office Deduction threshold changed' },
  { timestamp: '2026-01-15 14:15:33', description: 'Chime account \'Sarah Chen\' flagged for review — purchase sign mismatch' },
  { timestamp: '2026-01-15 13:58:42', description: 'ML model retrained — confidence improved 1.8%' },
  { timestamp: '2026-01-15 13:45:11', description: 'QIF export completed — Client #1847' },
];

// ML Category Metrics
export interface CategoryMetric {
  category: string;
  precision: number;
  recall: number;
}

export const mlCategoryMetrics: CategoryMetric[] = [
  { category: 'Office Supplies', precision: 96.2, recall: 94.1 },
  { category: 'Meals & Entertainment', precision: 89.4, recall: 91.2 },
  { category: 'Travel', precision: 93.7, recall: 95.8 },
  { category: 'Software', precision: 97.1, recall: 96.3 },
  { category: 'Professional Services', precision: 91.5, recall: 89.7 },
  { category: 'Equipment', precision: 94.8, recall: 93.2 },
  { category: 'Utilities', precision: 88.3, recall: 90.1 },
];

// Model Versions
export interface ModelVersion {
  version: string;
  accuracy: number;
  status: 'Production' | 'Rolled Back' | 'Deprecated';
  date: string;
}

export const modelVersions: ModelVersion[] = [
  { version: 'v3.5.4', accuracy: 94.2, status: 'Production', date: '2026-01-15' },
  { version: 'v3.5.3', accuracy: 92.8, status: 'Rolled Back', date: '2026-01-14' },
  { version: 'v3.5.2', accuracy: 93.1, status: 'Deprecated', date: '2026-01-10' },
  { version: 'v3.5.1', accuracy: 91.7, status: 'Deprecated', date: '2026-01-05' },
];

// Export Formats
export interface ExportFormat {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  status: 'Available' | 'Coming Soon';
}

export const exportFormats: ExportFormat[] = [
  { id: 'qif', name: 'QIF Format', description: 'Quicken Interchange Format for QuickBooks, MoneyDance, and HomeBank.', icon: 'FileOutput', color: '#C9A96E', status: 'Available' },
  { id: 'csv', name: 'CSV Format', description: 'Comma-separated values with full category mapping and tax tags.', icon: 'Table', color: '#60A5FA', status: 'Available' },
  { id: 'excel', name: 'Excel Format', description: 'Multi-sheet workbook with summary, transactions, and tax schedule.', icon: 'Grid3x3', color: '#4ADE80', status: 'Available' },
  { id: 'ofx', name: 'OFX Format', description: 'Open Financial Exchange for direct bank import.', icon: 'FileText', color: '#FBBF24', status: 'Coming Soon' },
  { id: 'json', name: 'JSON Format', description: 'Machine-readable output with full audit metadata.', icon: 'Braces', color: '#F87171', status: 'Available' },
  { id: 'pdf', name: 'PDF Summary', description: 'Client-ready summary report with charts and breakdowns.', icon: 'FileCheck', color: '#C9A96E', status: 'Available' },
];

// Linked Accounts
export interface LinkedAccount {
  nickname: string;
  institution: string;
  accountType: string;
  lastSync: string;
  status: 'Connected' | 'Error' | 'Pending';
  fragilityScore: number;
}

export const linkedAccounts: LinkedAccount[] = [
  { nickname: 'Primary Checking', institution: 'Chime', accountType: 'Checking', lastSync: '2026-01-15 14:30:00', status: 'Connected', fragilityScore: 15 },
  { nickname: 'Business Savings', institution: 'Wells Fargo', accountType: 'Savings', lastSync: '2026-01-15 14:15:00', status: 'Connected', fragilityScore: 22 },
  { nickname: 'Cash App Business', institution: 'Cash App', accountType: 'Checking', lastSync: '2026-01-15 13:45:00', status: 'Connected', fragilityScore: 35 },
  { nickname: 'Credit Line', institution: 'TD Bank', accountType: 'Credit', lastSync: '2026-01-14 18:20:00', status: 'Error', fragilityScore: 78 },
  { nickname: 'Operating Account', institution: 'Chase', accountType: 'Checking', lastSync: '2026-01-15 12:00:00', status: 'Connected', fragilityScore: 18 },
];

// Test Results
export interface TestResult {
  name: string;
  category: string;
  status: 'PASS' | 'FAIL' | 'SKIP';
  duration: string;
  details: string;
}

export const testResults: TestResult[] = [
  { name: 'test_chime_pdf_parser', category: 'Parser', status: 'PASS', duration: '0.42s', details: 'Successfully parsed 47 transactions from Chime PDF statement' },
  { name: 'test_wells_fargo_csv_parser', category: 'Parser', status: 'PASS', duration: '0.31s', details: 'Parsed 234 transactions with 100% field extraction' },
  { name: 'test_cashapp_parser', category: 'Parser', status: 'PASS', duration: '0.28s', details: 'Handled Cash App CSV with Bitcoin transactions' },
  { name: 'test_ml_categorizer_accuracy', category: 'ML', status: 'PASS', duration: '12.4s', details: 'Overall accuracy: 94.2% (threshold: 90%)' },
  { name: 'test_tax_rule_home_office', category: 'Tax Rule', status: 'PASS', duration: '0.08s', details: 'Rule TAX-RULE-001 applied correctly to S-Corp entity' },
  { name: 'test_tax_rule_qbi_deduction', category: 'Tax Rule', status: 'PASS', duration: '0.11s', details: '20% QBI deduction calculated for Partnership' },
  { name: 'test_s_corp_category_mapping', category: 'Tax Rule', status: 'PASS', duration: '0.11s', details: 'Health insurance correctly mapped for >2% shareholder' },
  { name: 'test_qif_export_format', category: 'Export', status: 'PASS', duration: '0.15s', details: 'QIF output validated against HomeBank import' },
  { name: 'test_excel_multi_sheet', category: 'Export', status: 'PASS', duration: '0.38s', details: '3-sheet workbook generated with correct formulas' },
  { name: 'test_multi_account_fragility', category: 'Fragility', status: 'PASS', duration: '0.22s', details: 'Fragility scores calculated within expected range' },
  { name: 'test_purchase_sign_chime', category: 'Parser', status: 'PASS', duration: '0.18s', details: 'Chime negative purchase signs correctly interpreted' },
  { name: 'test_client_isolation', category: 'Security', status: 'PASS', duration: '0.05s', details: 'Cross-client data access blocked at all layers' },
  { name: 'test_audit_log_immutability', category: 'Security', status: 'PASS', duration: '0.09s', details: 'Log tamper detection verified' },
  { name: 'test_incremental_ml_training', category: 'ML', status: 'PASS', duration: '245.2s', details: 'Model updated with 1,847 new samples, accuracy +1.8%' },
  { name: 'test_partnership_schedule_k', category: 'Tax Rule', status: 'SKIP', duration: '0.03s', details: 'Schedule K-1 support scheduled for v3.6' },
  { name: 'test_ofx_export', category: 'Export', status: 'SKIP', duration: '0.01s', details: 'OFX export not yet implemented' },
];
