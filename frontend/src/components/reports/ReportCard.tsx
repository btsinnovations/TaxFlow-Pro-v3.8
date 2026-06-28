import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Download, FileText } from "lucide-react";

interface ReportCardProps {
  title: string;
  data: Record<string, unknown> | Record<string, unknown>[];
  onExport?: () => void;
  exportLabel?: string;
}

export function ReportCard({ title, data, onExport, exportLabel = "Export" }: ReportCardProps) {
  const isEmpty = !data || (Array.isArray(data) ? data.length === 0 : Object.keys(data).length === 0);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-lg flex items-center gap-2">
          <FileText className="h-5 w-5 text-muted-foreground" />
          {title}
        </CardTitle>
        {onExport && !isEmpty && (
          <Button variant="outline" size="sm" onClick={onExport}>
            <Download className="h-3 w-3 mr-1" />
            {exportLabel}
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {isEmpty ? (
          <p className="text-sm text-muted-foreground text-center py-8">No data. Run the report to see results.</p>
        ) : (
          <pre className="text-xs overflow-x-auto bg-muted/30 rounded-md p-3">
            {JSON.stringify(data, null, 2)}
          </pre>
        )}
      </CardContent>
    </Card>
  );
}