import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const ROW_KEYS = ["a", "b", "c", "d", "e"] as const;

export function ActivityCard() {
  return (
    <Card data-slot="card" data-testid="table-card" className="relative">
      <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
        <div className="space-y-1">
          <CardTitle>Actividad reciente</CardTitle>
          <CardDescription>
            Últimas ventas, transferencias y movimientos de inventario.
          </CardDescription>
        </div>
        <Badge variant="outline" className="rounded-md text-xs">
          Próximamente
        </Badge>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3" aria-hidden="true">
          {ROW_KEYS.map((k) => (
            <li key={k} className="flex items-center gap-3">
              <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-3 w-1/2" />
                <Skeleton className="h-3 w-3/4" />
              </div>
              <Skeleton className="h-3 w-16" />
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
