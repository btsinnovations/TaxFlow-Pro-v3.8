import { AuthProvider } from "@/context/AuthContext";
import { ToastProvider } from "@/context/ToastContext";
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

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <div className="min-h-screen bg-canvas text-text-primary">
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
        </div>
        <ToastContainer />
      </ToastProvider>
    </AuthProvider>
  );
}
