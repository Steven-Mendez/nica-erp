import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function SettingsRoute() {
  useDocumentTitle("Configuración");
  return (
    <AppShell>
      <Card className="mx-auto max-w-xl">
        <CardHeader>
          <CardTitle>Configuración</CardTitle>
          <CardDescription>Próximamente.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Aquí aparecerán las preferencias del espacio de trabajo.
        </CardContent>
      </Card>
    </AppShell>
  );
}
