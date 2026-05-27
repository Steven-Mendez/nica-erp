// apps/web/src/components/ui/label.tsx
//
// Plain `<label>` styled to match shadcn's Label primitive. We skip
// `@radix-ui/react-label` because the only thing it adds over a vanilla label
// is the same `htmlFor`-driven focus behaviour the browser already gives us,
// so the extra dependency isn't worth it for this codebase.
import { forwardRef, type LabelHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export type LabelProps = LabelHTMLAttributes<HTMLLabelElement>;

export const Label = forwardRef<HTMLLabelElement, LabelProps>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn(
      "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
      className,
    )}
    {...props}
  />
));
Label.displayName = "Label";
