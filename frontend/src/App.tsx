import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ToastProvider } from "@/context/ToastContext";
import { Routes, Route } from "react-router";
import ToastContainer from "@/components/ToastContainer";
import { BootGate } from "@/components/BootGate";
import Navigation from './sections/Navigation';
import Hero from './sections/Hero';
import UploadSection from './sections/UploadSection';
import DashboardOverview from './sections/DashboardOverview';
import ClientManagement from './sections/ClientManagement';
import TaxRules from './sections/TaxRules';
import AuditTrail from './sections/AuditTrail';
import MLTraining from './sections/MLTraining';
import ExportFormats from './sections/ExportFormats';
import MultiAccount from './sections/MultiAccount';
import TestSuite from './sections/TestSuite';
import ProcessedFiles from './sections/ProcessedFiles';
import Footer from './sections/Footer';
import {
  AuditManager,
  BackupManager,
  BankReconciliation,
  BudgetForecast,
  CheckRegister,
  ClientManager,
  COAManager,
  DashboardHealth,
  DepreciationManager,
  ExportManager,
  FlagManager,
  GLManager,
  ImportsManager,
  InvestmentsManager,
  InvoicingManager,
  LiabilitiesManager,
  MileageLog,
  MultiCurrency,
  PeriodManager,
  RecurringRules,
  Register,
  ReportsCenter,
  RuleManager,
  SalesTaxManager,
  TaxFilingExports,
  TaxManager,
  UploadManager,
  VendorManager,
  YearEndManager,
} from "@/components/v3.11";

function LandingPage() {
  return (
    <>
      <Navigation />
      <main>
        <Hero />
        <UploadSection />
        <DashboardOverview />
        <ClientManagement />
        <TaxRules />
        <AuditTrail />
        <MLTraining />
        <ExportFormats />
        <MultiAccount />
        <TestSuite />
        <ProcessedFiles />
      </main>
      <Footer />
    </>
  );
}

function AuthenticatedRoutes() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return null;
  if (!isAuthenticated) return <BootGate children={<LandingPage />} />;
  return <LandingPage />;
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <div className="min-h-screen bg-canvas text-text-primary">
          <Routes>
            <Route path="/" element={<AuthenticatedRoutes />} />
            <Route path="/accounts" element={<COAManager />} />
            <Route path="/audit" element={<AuditManager />} />
            <Route path="/backup" element={<BackupManager />} />
            <Route path="/budget-forecast" element={<BudgetForecast />} />
            <Route path="/check-register" element={<CheckRegister />} />
            <Route path="/clients" element={<ClientManager />} />
            <Route path="/depreciation" element={<DepreciationManager />} />
            <Route path="/export" element={<ExportManager />} />
            <Route path="/flags" element={<FlagManager />} />
            <Route path="/gl" element={<GLManager />} />
            <Route path="/health" element={<DashboardHealth />} />
            <Route path="/imports" element={<ImportsManager />} />
            <Route path="/investments" element={<InvestmentsManager />} />
            <Route path="/invoicing" element={<InvoicingManager />} />
            <Route path="/liabilities" element={<LiabilitiesManager />} />
            <Route path="/mileage" element={<MileageLog />} />
            <Route path="/multi-currency" element={<MultiCurrency />} />
            <Route path="/periods" element={<PeriodManager />} />
            <Route path="/recurring" element={<RecurringRules />} />
            <Route path="/register" element={<Register />} />
            <Route path="/reconciliation" element={<BankReconciliation />} />
            <Route path="/reports" element={<ReportsCenter />} />
            <Route path="/rules" element={<RuleManager />} />
            <Route path="/sales-tax" element={<SalesTaxManager />} />
            <Route path="/tax" element={<TaxManager />} />
            <Route path="/tax-exports" element={<TaxFilingExports />} />
            <Route path="/upload" element={<UploadManager />} />
            <Route path="/vendors" element={<VendorManager />} />
            <Route path="/year-end" element={<YearEndManager />} />
          </Routes>
        </div>
        <ToastContainer />
      </ToastProvider>
    </AuthProvider>
  );
}
