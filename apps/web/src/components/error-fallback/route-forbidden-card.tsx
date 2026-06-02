import { ShieldOff } from "lucide-react";
import { Card } from "@/components/ui/card";
import { RecoveryLink } from "./recovery-link";

export function RouteForbiddenCard() {
  return (
    <Card className="mx-auto my-12 max-w-md p-6" role="alert">
      <div className="flex items-start gap-4">
        <ShieldOff className="size-6 text-destructive" aria-hidden />
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">No tienes permiso para ver esto</h2>
          <p className="text-sm text-muted-foreground">
            Tu rol actual no incluye este recurso. Si crees que es un error,
            pide a un administrador de la empresa que te dé acceso.
          </p>
          <RecoveryLink>Volver al inicio</RecoveryLink>
        </div>
      </div>
    </Card>
  );
}
