import type { ReactNode } from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type Delta = {
  value: string;
  direction: "up" | "down";
};

type KpiCardProps = {
  label: string;
  value?: string;
  delta?: Delta;
  hint?: ReactNode;
  hintIcon?: ReactNode;
  className?: string;
  testId?: string;
};

export function KpiCard({ label, value, delta, hint, hintIcon, className, testId }: KpiCardProps) {
  const isPlaceholder = value === undefined;
  return (
    <Card
      data-slot="card"
      data-testid={testId ?? "kpi-card"}
      className={cn("relative overflow-hidden", className)}
    >
      <CardHeader className="gap-1.5">
        <CardDescription>{label}</CardDescription>
        {isPlaceholder ? (
          <Skeleton className="h-8 w-28" />
        ) : (
          <CardTitle className="text-2xl font-semibold tabular-nums lg:text-3xl">{value}</CardTitle>
        )}
        <div className="absolute right-4 top-4">
          {isPlaceholder ? (
            <Badge variant="outline" className="rounded-md text-xs">
              Próximamente
            </Badge>
          ) : delta !== undefined ? (
            <Badge
              variant={delta.direction === "up" ? "ok" : "warn"}
              className="flex gap-1 rounded-md text-xs"
            >
              {delta.direction === "up" ? (
                <TrendingUp className="h-3 w-3" aria-hidden="true" />
              ) : (
                <TrendingDown className="h-3 w-3" aria-hidden="true" />
              )}
              {delta.value}
            </Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardFooter className="flex-col items-start gap-1 pt-0 text-sm">
        {isPlaceholder ? (
          <Skeleton className="h-4 w-32" />
        ) : (
          <div className="flex items-center gap-2 font-medium">
            {hint}
            {hintIcon}
          </div>
        )}
      </CardFooter>
    </Card>
  );
}
