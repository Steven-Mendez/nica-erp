import {
  forwardRef,
  useEffect,
  useState,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { cn } from "@/lib/utils";
import { useSidebar } from "./sidebar-context";

export const SIDEBAR_WIDTH_EXPANDED = "16rem";
export const SIDEBAR_WIDTH_COLLAPSED = "3.5rem";

export const SIDEBAR_ROOT_ID = "app-sidebar";

// True while the viewport is below the md breakpoint (768px). The
// closed-mobile a11y trio (aria-hidden + inert + hidden) only fires
// in that regime — at md+ the sidebar is always visible and tab-
// reachable. We watch `matchMedia` so device rotation flips the
// guards without a re-render of the consuming tree.
function useIsMobileViewport(): boolean {
  const [isMobile, setIsMobile] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia("(max-width: 767px)").matches;
  });
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(max-width: 767px)");
    const onChange = () => setIsMobile(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return isMobile;
}

export function Sidebar({ className, children, ...props }: HTMLAttributes<HTMLElement>) {
  const { state, mobileOpen, setMobileOpen } = useSidebar();
  const isMobile = useIsMobileViewport();

  // Closed-mobile guard: when the sidebar is closed AND the viewport
  // is in the mobile regime, the entire panel is removed from the
  // a11y tree (aria-hidden), made non-interactive (inert), and
  // hidden from layout (display:none via Tailwind's `hidden`). The
  // three guards cover screen-reader users, keyboard users, and CSS
  // size-respecting consumers respectively. When the sidebar opens
  // or the viewport widens, every guard is removed.
  const hideFromMobile = isMobile && !mobileOpen;

  return (
    <>
      <div
        data-state={mobileOpen ? "open" : "closed"}
        className="fixed inset-0 z-30 bg-black/40 data-[state=closed]:pointer-events-none data-[state=closed]:opacity-0 md:hidden transition-opacity"
        onClick={() => setMobileOpen(false)}
        aria-hidden="true"
      />
      <aside
        id={SIDEBAR_ROOT_ID}
        data-sidebar="root"
        data-state={state}
        data-mobile-state={mobileOpen ? "open" : "closed"}
        aria-hidden={hideFromMobile ? "true" : undefined}
        // `inert` is set as a string attribute because TS DOM types
        // pre-date the property; React accepts the empty string and
        // emits the boolean attribute correctly.
        {...(hideFromMobile ? ({ inert: "" } as Record<string, string>) : {})}
        style={{
          ["--sidebar-width" as string]:
            state === "expanded" ? SIDEBAR_WIDTH_EXPANDED : SIDEBAR_WIDTH_COLLAPSED,
        }}
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex h-screen flex-col border-r bg-sidebar text-sidebar-foreground transition-[width,transform] duration-200 ease-out",
          "w-[var(--sidebar-width)]",
          "data-[mobile-state=closed]:-translate-x-full md:data-[mobile-state=closed]:translate-x-0",
          "md:sticky md:translate-x-0",
          hideFromMobile && "hidden",
          className,
        )}
        {...props}
      >
        {children}
      </aside>
    </>
  );
}

export const SidebarHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      data-sidebar="header"
      className={cn(
        "flex h-14 shrink-0 items-center gap-2 border-b border-sidebar-border px-2",
        className,
      )}
      {...props}
    />
  ),
);
SidebarHeader.displayName = "SidebarHeader";

export const SidebarContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      data-sidebar="content"
      className={cn(
        "flex-1 overflow-y-auto overflow-x-hidden p-2 [&::-webkit-scrollbar]:w-1.5",
        className,
      )}
      {...props}
    />
  ),
);
SidebarContent.displayName = "SidebarContent";

export const SidebarFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      data-sidebar="footer"
      className={cn("flex flex-col gap-1 border-t border-sidebar-border p-2", className)}
      {...props}
    />
  ),
);
SidebarFooter.displayName = "SidebarFooter";

export const SidebarGroup = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      data-sidebar="group"
      className={cn("flex flex-col gap-1 py-1", className)}
      {...props}
    />
  ),
);
SidebarGroup.displayName = "SidebarGroup";

export const SidebarGroupLabel = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => {
    const { state } = useSidebar();
    return (
      <div
        ref={ref}
        data-sidebar="group-label"
        data-state={state}
        className={cn(
          "px-2 py-1 text-xs font-medium uppercase tracking-wider text-sidebar-foreground/60",
          "data-[state=collapsed]:opacity-0 data-[state=collapsed]:pointer-events-none transition-opacity",
          className,
        )}
        {...props}
      />
    );
  },
);
SidebarGroupLabel.displayName = "SidebarGroupLabel";

export function SidebarMenu({ className, ...props }: HTMLAttributes<HTMLUListElement>) {
  return <ul data-sidebar="menu" className={cn("flex flex-col gap-0.5", className)} {...props} />;
}

export function SidebarMenuItem({ className, ...props }: HTMLAttributes<HTMLLIElement>) {
  return <li data-sidebar="menu-item" className={cn("relative list-none", className)} {...props} />;
}

export interface SidebarMenuButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  icon?: ReactNode;
  label?: ReactNode;
}

export const SidebarMenuButton = forwardRef<HTMLButtonElement, SidebarMenuButtonProps>(
  ({ className, active = false, icon, label, children, title, ...props }, ref) => {
    const { state } = useSidebar();
    const tooltip = state === "collapsed" && typeof label === "string" ? label : title;
    return (
      <button
        ref={ref}
        type="button"
        data-active={active ? "true" : "false"}
        data-state={state}
        title={tooltip}
        className={cn(
          "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm",
          "text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
          "data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground data-[active=true]:font-medium",
          "data-[state=collapsed]:justify-center data-[state=collapsed]:px-0",
          "transition-colors",
          className,
        )}
        {...props}
      >
        {icon !== undefined ? (
          <span className="flex h-5 w-5 shrink-0 items-center justify-center">{icon}</span>
        ) : null}
        <span
          data-state={state}
          className="flex-1 truncate text-left data-[state=collapsed]:hidden"
        >
          {label !== undefined ? label : children}
        </span>
      </button>
    );
  },
);
SidebarMenuButton.displayName = "SidebarMenuButton";

// Multi-level sub-menu primitives. The shadcn upstream emits
// SidebarMenuSub as a <ul> with indented children and a left rule
// for active state. We mirror that surface so future shadcn updates
// land cleanly.
export function SidebarMenuSub({ className, ...props }: HTMLAttributes<HTMLUListElement>) {
  const { state } = useSidebar();
  return (
    <ul
      data-sidebar="menu-sub"
      data-state={state}
      className={cn(
        "ml-7 mt-0.5 flex flex-col gap-0.5 border-l border-sidebar-border pl-2",
        "data-[state=collapsed]:hidden",
        className,
      )}
      {...props}
    />
  );
}

export function SidebarMenuSubItem({ className, ...props }: HTMLAttributes<HTMLLIElement>) {
  return (
    <li data-sidebar="menu-sub-item" className={cn("relative list-none", className)} {...props} />
  );
}

export interface SidebarMenuSubButtonProps extends HTMLAttributes<HTMLSpanElement> {
  active?: boolean;
  label?: ReactNode;
}

// Rendered as a <span> so a wrapping `<Link>` (which itself renders an
// <a>) does not produce nested anchors. The parent Link supplies the
// actual click target.
export const SidebarMenuSubButton = forwardRef<HTMLSpanElement, SidebarMenuSubButtonProps>(
  ({ className, active = false, label, children, ...props }, ref) => {
    return (
      <span
        ref={ref}
        data-active={active ? "true" : "false"}
        className={cn(
          "flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs",
          "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
          "data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground data-[active=true]:font-medium",
          "transition-colors",
          className,
        )}
        {...props}
      >
        <span className="flex-1 truncate text-left">{label !== undefined ? label : children}</span>
      </span>
    );
  },
);
SidebarMenuSubButton.displayName = "SidebarMenuSubButton";

export function SidebarSeparator({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-sidebar="separator"
      className={cn("mx-2 my-1 h-px bg-sidebar-border", className)}
      {...props}
    />
  );
}

export function SidebarInset({ className, children }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-sidebar="inset"
      className={cn("flex min-h-screen min-w-0 flex-1 flex-col bg-background", className)}
    >
      {children}
    </div>
  );
}
