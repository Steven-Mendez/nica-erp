import { AlertTriangle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { RecoveryLink } from "./recovery-link";

export function RouteRuntimeErrorCard() {
  return (
    <Card className="mx-auto my-12 max-w-md p-6" role="alert">
      <div className="flex items-start gap-4">
        <AlertTriangle className="size-6 text-destructive" aria-hidden />
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Ocurrió un error inesperado</h2>
          <p className="text-sm text-muted-foreground">
            Algo falló al cargar esta pantalla. Vuelve a intentarlo en unos segundos. Si el problema
            persiste, contacta al equipo técnico.
          </p>
          <RecoveryLink>Volver al inicio</RecoveryLink>
        </div>
      </div>
    </Card>
  );
}
