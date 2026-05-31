import { Link, useNavigate } from "@tanstack/react-router";
import { LogOut, UserRound } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { useLogoutMutation, useMeQuery } from "@/features/auth/api/hooks";
import { cn } from "@/lib/utils";

function initialsOf(name: string): string {
  const parts = name
    .trim()
    .split(/\s+/)
    .filter((p) => p.length > 0);
  const first = parts[0]?.charAt(0) ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1]?.charAt(0) ?? "") : "";
  const initials = (first + last).toUpperCase();
  return initials.length > 0 ? initials : "?";
}

const AVATAR_PALETTE = [
  "#E53935",
  "#D81B60",
  "#8E24AA",
  "#3949AB",
  "#1E88E5",
  "#039BE5",
  "#00897B",
  "#43A047",
  "#7CB342",
  "#FB8C00",
  "#F4511E",
  "#6D4C41",
] as const;

function avatarColor(key: string): string {
  let hash = 0;
  for (let i = 0; i < key.length; i += 1) {
    hash = (hash * 31 + key.charCodeAt(i)) | 0;
  }
  const idx = Math.abs(hash) % AVATAR_PALETTE.length;
  return AVATAR_PALETTE[idx] ?? AVATAR_PALETTE[0];
}

export function AccountMenu() {
  const me = useMeQuery();
  const logout = useLogoutMutation();
  const navigate = useNavigate();

  if (me.isLoading) {
    return <Skeleton className="h-8 w-8 rounded-full" />;
  }
  if (me.isError || me.data === undefined) {
    return null;
  }

  const displayName = me.data.display_name?.trim() || me.data.email;
  const initials = initialsOf(displayName);
  const bgColor = avatarColor(me.data.email);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Menú de cuenta"
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold uppercase tracking-wide text-white",
          "focus:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        )}
        style={{ backgroundColor: bgColor }}
        title={displayName}
      >
        {initials}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel>
          <div className="flex flex-col gap-0.5 leading-tight">
            <span className="truncate text-sm font-medium">{displayName}</span>
            <span className="truncate text-xs font-normal text-muted-foreground">
              {me.data.email}
            </span>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/account" className="cursor-pointer">
            <UserRound className="h-4 w-4" aria-hidden="true" />
            <span>Cuenta</span>
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={(e) => {
            e.preventDefault();
            logout.mutate(undefined, {
              onSettled: () => {
                void navigate({ to: "/login" });
              },
            });
          }}
          disabled={logout.isPending}
          className="cursor-pointer text-destructive focus:text-destructive"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          <span>{logout.isPending ? "Cerrando sesión…" : "Cerrar sesión"}</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
