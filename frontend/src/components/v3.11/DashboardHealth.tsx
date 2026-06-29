import { useEffect, useState } from "react";
import ModuleShell from "./ModuleShell";
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import { getHealth, getHealthMigrations, getHealthConfig, getHealthBootstrap, getHealthEchoAuth } from "@/hooks/useAPIExtensions";
import { Loader2, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

interface HealthCheck {
  name: string;
  status: "ok" | "error" | "loading";
  detail?: string;
}

export default function DashboardHealth() {
  const [checks, setChecks] = useState<HealthCheck[]>([
    { name: "General Health", status: "loading" },
    { name: "Migrations", status: "loading" },
    { name: "Config", status: "loading" },
    { name: "Bootstrap", status: "loading" },
    { name: "Echo Auth", status: "loading" },
  ]);

  useEffect(() => {
    const updates: HealthCheck[] = [...checks];

    getHealth().then((d) => {
      updates[0] = { name: "General Health", status: "ok", detail: JSON.stringify(d).slice(0, 200) };
      setChecks([...updates]);
    }).catch((e) => { updates[0] = { name: "General Health", status: "error", detail: e.message }; setChecks([...updates]); });

    getHealthMigrations().then((d) => {
      updates[1] = { name: "Migrations", status: "ok", detail: JSON.stringify(d).slice(0, 200) };
      setChecks([...updates]);
    }).catch((e) => { updates[1] = { name: "Migrations", status: "error", detail: e.message }; setChecks([...updates]); });

    getHealthConfig().then((d) => {
      updates[2] = { name: "Config", status: "ok", detail: JSON.stringify(d).slice(0, 200) };
      setChecks([...updates]);
    }).catch((e) => { updates[2] = { name: "Config", status: "error", detail: e.message }; setChecks([...updates]); });

    getHealthBootstrap().then((d) => {
      updates[3] = { name: "Bootstrap", status: "ok", detail: JSON.stringify(d).slice(0, 200) };
      setChecks([...updates]);
    }).catch((e) => { updates[3] = { name: "Bootstrap", status: "error", detail: e.message }; setChecks([...updates]); });

    getHealthEchoAuth().then((d) => {
      updates[4] = { name: "Echo Auth", status: "ok", detail: JSON.stringify(d).slice(0, 200) };
      setChecks([...updates]);
    }).catch((e) => { updates[4] = { name: "Echo Auth", status: "error", detail: e.message }; setChecks([...updates]); });
  }, []);

  return (
    <ModuleShell title="Dashboard Health" description="System health checks for migrations, config, bootstrap, and auth." moduleId="M05">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {checks.map((c) => (
          <Card key={c.name} className="bg-canvas border-divider">
            <CardHeader>
              <CardTitle className="text-text-primary text-base flex items-center gap-2">
                {c.status === "loading" && <Loader2 className="w-4 h-4 animate-spin text-gold" />}
                {c.status === "ok" && <CheckCircle2 className="w-4 h-4 text-green-400" />}
                {c.status === "error" && <XCircle className="w-4 h-4 text-red-400" />}
                {c.name}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {c.status === "loading" && <p className="text-text-secondary text-sm">Checking...</p>}
              {c.status === "ok" && <p className="text-green-300 text-sm break-all">{c.detail || "OK"}</p>}
              {c.status === "error" && (
                <p className="text-red-300 text-sm break-all flex items-start gap-1">
                  <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                  {c.detail}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </ModuleShell>
  );
}