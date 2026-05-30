import { cn } from "@/lib/utils";

type LogoProps = {
  className?: string;
  size?: number;
  withWordmark?: boolean;
};

export function Logo({ className, size = 32, withWordmark = false }: LogoProps) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span
        aria-label="Nica ERP"
        role="img"
        className="inline-flex shrink-0 items-center justify-center rounded-md bg-primary font-bold text-primary-foreground"
        style={{ width: size, height: size, fontSize: Math.round(size * 0.55) }}
      >
        N
      </span>
      {withWordmark ? (
        <span className="text-base font-semibold tracking-tight text-foreground">Nica ERP</span>
      ) : null}
    </span>
  );
}
