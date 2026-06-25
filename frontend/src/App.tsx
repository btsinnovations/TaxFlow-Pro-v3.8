import { AuthProvider } from "@/context/AuthContext";
import { ToastProvider } from "@/context/ToastContext";
import { Routes, Route } from "react-router";
import ToastContainer from "@/components/ToastContainer";
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
  CheckRegister,
  LiabilitiesInvestments,
  InventoryProjects,
  MultiCurrency,
  BankReconciliation,
  TaxFilingExports,
  ReportsCenter,
  BudgetForecast,
  InvoicingAPAR,
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

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <div className="min-h-screen bg-canvas text-text-primary">
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/check-register" element={<CheckRegister />} />
            <Route path="/liabilities" element={<LiabilitiesInvestments />} />
            <Route path="/inventory-projects" element={<InventoryProjects />} />
            <Route path="/multi-currency" element={<MultiCurrency />} />
            <Route path="/reconciliation" element={<BankReconciliation />} />
            <Route path="/tax-exports" element={<TaxFilingExports />} />
            <Route path="/reports" element={<ReportsCenter />} />
            <Route path="/budget-forecast" element={<BudgetForecast />} />
            <Route path="/invoicing" element={<InvoicingAPAR />} />
          </Routes>
        </div>
        <ToastContainer />
      </ToastProvider>
    </AuthProvider>
  );
}
