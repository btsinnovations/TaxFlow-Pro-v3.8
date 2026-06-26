import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useNavigate } from "react-router-dom";

interface ModuleShellProps {
  title: string;
  description: string;
  moduleId: string;
  children?: React.ReactNode;
}

export default function ModuleShell({ title, description, moduleId, children }: ModuleShellProps) {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-canvas text-text-primary p-6">
      <div className="max-w-[1440px] mx-auto">
        <div className="mb-6 flex items-center gap-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate("/")}
            className="border-gold/30 text-gold hover:bg-gold/10"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="font-serif text-3xl text-gold">{title}</h1>
            <p className="text-text-secondary text-sm">Module {moduleId} — scaffolded for v3.11</p>
          </div>
        </div>

        <Card className="bg-canvas border-divider">
          <CardHeader>
            <CardTitle className="text-text-primary">{title}</CardTitle>
            <CardDescription className="text-text-secondary">{description}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {children ?? (
              <div className="rounded-lg border border-dashed border-divider p-8 text-center">
                <p className="text-text-secondary">
                  Backend wiring not yet connected. This shell is ready for domain logic integration.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
