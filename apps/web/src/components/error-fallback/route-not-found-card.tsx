import { Compass } from "lucide-react";
import { Card } from "@/components/ui/card";
import { RecoveryLink } from "./recovery-link";

export function RouteNotFoundCard() {
  return (
    <Card className="mx-auto my-12 max-w-md p-6" role="alert">
      <div className="flex items-start gap-4">
        <Compass className="size-6 text-muted-foreground" aria-hidden />
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">No encontramos esa página</h2>
          <p className="text-sm text-muted-foreground">
            La URL que abriste no corresponde a ninguna sección de la app.
            Puede que el enlace esté desactualizado.
          </p>
          <RecoveryLink>Volver al inicio</RecoveryLink>
        </div>
      </div>
    </Card>
  );
}
