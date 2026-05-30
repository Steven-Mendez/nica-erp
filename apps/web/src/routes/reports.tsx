import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function ReportsRoute() {
  useDocumentTitle("Reportes");
  return (
    <AppShell>
      <Card className="mx-auto max-w-xl">
        <CardHeader>
          <CardTitle>Reportes</CardTitle>
          <CardDescription>Próximamente.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Aquí aparecerán impuestos, pagos y reportes fiscales.
        </CardContent>
      </Card>
    </AppShell>
  );
}
