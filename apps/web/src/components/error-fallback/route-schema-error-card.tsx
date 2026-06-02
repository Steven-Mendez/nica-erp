import { FileWarning } from "lucide-react";
import { Card } from "@/components/ui/card";
import { RecoveryLink } from "./recovery-link";

export function RouteSchemaErrorCard() {
  return (
    <Card className="mx-auto my-12 max-w-md p-6" role="alert">
      <div className="flex items-start gap-4">
        <FileWarning className="size-6 text-destructive" aria-hidden />
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Respuesta inesperada del servidor</h2>
          <p className="text-sm text-muted-foreground">
            La respuesta del servidor no tiene el formato esperado.
            Si el problema persiste, reporta el incidente al equipo técnico.
          </p>
          <RecoveryLink>Volver al inicio</RecoveryLink>
        </div>
      </div>
    </Card>
  );
}
