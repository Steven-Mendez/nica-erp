import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function SalesRoute() {
  useDocumentTitle("Ventas");
  return (
    <AppShell>
      <Card className="mx-auto max-w-xl">
        <CardHeader>
          <CardTitle>Ventas</CardTitle>
          <CardDescription>Próximamente.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Aquí aparecerán clientes, facturas y notas de crédito.
        </CardContent>
      </Card>
    </AppShell>
  );
}
