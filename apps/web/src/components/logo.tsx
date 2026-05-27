import { cn } from "@/lib/utils";

type LogoProps = {
  className?: string;
  size?: number;
  withWordmark?: boolean;
};

export function Logo({ className, size = 32, withWordmark = false }: LogoProps) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 32 32"
        width={size}
        height={size}
        role="img"
        aria-label="Nica ERP"
        className="text-foreground"
      >
        <rect width="32" height="32" rx="6" className="fill-foreground" />
        <text
          x="16"
          y="16"
          textAnchor="middle"
          dominantBaseline="central"
          fontFamily="system-ui, -apple-system, Segoe UI, sans-serif"
          fontWeight={700}
          fontSize={20}
          className="fill-background"
        >
          N
        </text>
      </svg>
      {withWordmark ? (
        <span className="text-base font-semibold tracking-tight text-foreground">Nica ERP</span>
      ) : null}
    </span>
  );
}
