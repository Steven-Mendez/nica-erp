import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

type Range = "7d" | "30d" | "90d";

const RANGE_LABEL: Record<Range, string> = {
  "7d": "los últimos 7 días",
  "30d": "los últimos 30 días",
  "90d": "los últimos 3 meses",
};

export function TrendCard() {
  const [range, setRange] = useState<Range>("30d");

  return (
    <Card data-slot="card" data-testid="chart-card" className="relative">
      <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
        <div className="space-y-1">
          <CardTitle>Tendencia de ventas</CardTitle>
          <CardDescription>Ingresos diarios en {RANGE_LABEL[range]}.</CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <ToggleGroup
            type="single"
            value={range}
            onValueChange={(v) => {
              if (v === "7d" || v === "30d" || v === "90d") setRange(v);
            }}
            variant="outline"
            size="sm"
            className="hidden md:flex"
            aria-label="Rango de tiempo"
          >
            <ToggleGroupItem value="90d" className="h-8 px-2.5 text-xs">
              90d
            </ToggleGroupItem>
            <ToggleGroupItem value="30d" className="h-8 px-2.5 text-xs">
              30d
            </ToggleGroupItem>
            <ToggleGroupItem value="7d" className="h-8 px-2.5 text-xs">
              7d
            </ToggleGroupItem>
          </ToggleGroup>
          <Badge variant="outline" className="rounded-md text-xs">
            Próximamente
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <Skeleton className="h-64 w-full" />
      </CardContent>
    </Card>
  );
}
