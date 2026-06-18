import Hero from '@/sections/Hero';
import DashboardOverview from '@/sections/DashboardOverview';
import ClientManagement from '@/sections/ClientManagement';
import AuditTrail from '@/sections/AuditTrail';
import ExportFormats from '@/sections/ExportFormats';
import MultiAccount from '@/sections/MultiAccount';

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-canvas">
      <Hero />
      <DashboardOverview />
      <ClientManagement />
      <AuditTrail />
      <ExportFormats />
      <MultiAccount />
    </div>
  );
}
