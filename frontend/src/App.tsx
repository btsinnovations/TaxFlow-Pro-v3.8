import { Routes, Route } from 'react-router';
import { AuthProvider } from "@/context/AuthContext";
import { ToastProvider } from "@/context/ToastContext";
import { ClientProvider } from "@/context/ClientContext";
import ToastContainer from '@/components/ToastContainer';
import Navigation from './sections/Navigation';
import Footer from './sections/Footer';
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import ProcessedFilesPage from './pages/ProcessedFilesPage';
import TaxSummaryPage from './pages/TaxSummaryPage';
import TransactionsPage from './pages/TransactionsPage';
import BudgetsPage from './pages/BudgetsPage';
import ReceiptsPage from './pages/ReceiptsPage';
import SettingsPage from './pages/SettingsPage';
import JournalEntriesPage from './pages/JournalEntriesPage';
import PeriodsPage from './pages/PeriodsPage';
import ReportsPage from './pages/ReportsPage';
import ForecastPage from './pages/ForecastPage';
import DepreciationPage from './pages/DepreciationPage';
import BankConnectionsPage from './pages/BankConnectionsPage';
import BatchImportPage from './pages/BatchImportPage';
import ArchivePage from './pages/ArchivePage';
import ExchangeRatesPage from './pages/ExchangeRatesPage';
import EngagementsPage from './pages/EngagementsPage';

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <ClientProvider>
          <div className="min-h-screen bg-canvas text-text-primary">
            <Navigation />
            <main>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/upload" element={<Upload />} />
                <Route path="/processed-files" element={<ProcessedFilesPage />} />
                <Route path="/transactions" element={<TransactionsPage />} />
                <Route path="/tax-summary" element={<TaxSummaryPage />} />
                <Route path="/budgets" element={<BudgetsPage />} />
                <Route path="/receipts" element={<ReceiptsPage />} />
                <Route path="/journal-entries" element={<JournalEntriesPage />} />
                <Route path="/periods" element={<PeriodsPage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/forecast" element={<ForecastPage />} />
                <Route path="/depreciation" element={<DepreciationPage />} />
                <Route path="/bank-connections" element={<BankConnectionsPage />} />
                <Route path="/batch-import" element={<BatchImportPage />} />
                <Route path="/archive" element={<ArchivePage />} />
                <Route path="/exchange-rates" element={<ExchangeRatesPage />} />
                <Route path="/engagements" element={<EngagementsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </main>
            <Footer />
          </div>
          <ToastContainer />
        </ClientProvider>
      </ToastProvider>
    </AuthProvider>
  );
}
