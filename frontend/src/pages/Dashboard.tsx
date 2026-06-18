import Hero from '@/sections/Hero';
import DashboardOverview from '@/sections/DashboardOverview';
import ClientManagement from '@/sections/ClientManagement';
import TaxRules from '@/sections/TaxRules';
import AuditTrail from '@/sections/AuditTrail';
import MLTraining from '@/sections/MLTraining';
import ExportFormats from '@/sections/ExportFormats';
import MultiAccount from '@/sections/MultiAccount';
import TestSuite from '@/sections/TestSuite';

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-canvas">
      <Hero />
      <DashboardOverview />
      <ClientManagement />
      <TaxRules />
      <AuditTrail />
      <MLTraining />
      <ExportFormats />
      <MultiAccount />
      <TestSuite />
    </div>
  );
}
