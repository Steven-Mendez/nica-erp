import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function InventoryRoute() {
  useDocumentTitle("Inventario");
  return (
    <AppShell>
      <Card className="mx-auto max-w-xl">
        <CardHeader>
          <CardTitle>Inventario</CardTitle>
          <CardDescription>Próximamente.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Aquí aparecerán productos, kardex y movimientos de inventario.
        </CardContent>
      </Card>
    </AppShell>
  );
}
