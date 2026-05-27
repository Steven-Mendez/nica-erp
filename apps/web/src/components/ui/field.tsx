// apps/web/src/components/ui/field.tsx
//
// Field family — shadcn's modern form primitives. Composition:
//
//   <FieldGroup>
//     <Field data-invalid={fieldState.invalid}>
//       <FieldLabel htmlFor=...>Label</FieldLabel>
//       <Input ... aria-invalid={fieldState.invalid} />
//       <FieldDescription>Helper text</FieldDescription>
//       {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
//     </Field>
//   </FieldGroup>
//
// The `data-invalid` attribute is consumed by CSS to recolour Label and
// Description without prop drilling. Works hand-in-hand with `aria-invalid`
// on the actual control for accessibility.

import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type HTMLAttributes, type LabelHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

// ---------- Field (single field wrapper) ----------------------------------

const fieldVariants = cva("group/field", {
  variants: {
    orientation: {
      vertical: "flex flex-col gap-2",
      horizontal: "flex flex-row items-center gap-3",
      responsive: "flex flex-col gap-2 @md/field-group:flex-row @md/field-group:items-center",
    },
  },
  defaultVariants: { orientation: "vertical" },
});

export interface FieldProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof fieldVariants> {
  "data-invalid"?: boolean;
}

export const Field = forwardRef<HTMLDivElement, FieldProps>(
  ({ className, orientation, ...props }, ref) => (
    <div
      ref={ref}
      data-slot="field"
      className={cn(fieldVariants({ orientation }), className)}
      {...props}
    />
  ),
);
Field.displayName = "Field";

// ---------- FieldGroup (container for multiple fields) --------------------

export const FieldGroup = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      data-slot="field-group"
      className={cn("@container/field-group flex flex-col gap-6", className)}
      {...props}
    />
  ),
);
FieldGroup.displayName = "FieldGroup";

// ---------- FieldLabel ----------------------------------------------------

export const FieldLabel = forwardRef<HTMLLabelElement, LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      data-slot="field-label"
      className={cn(
        "flex items-center text-sm font-medium leading-none text-foreground",
        "group-data-[invalid=true]/field:text-destructive",
        "peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
        className,
      )}
      {...props}
    />
  ),
);
FieldLabel.displayName = "FieldLabel";

// ---------- FieldDescription ----------------------------------------------

export const FieldDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p
      ref={ref}
      data-slot="field-description"
      className={cn(
        "text-xs leading-snug text-muted-foreground",
        "group-data-[invalid=true]/field:text-destructive",
        className,
      )}
      {...props}
    />
  ),
);
FieldDescription.displayName = "FieldDescription";

// ---------- FieldError ----------------------------------------------------

interface FieldErrorIssue {
  message?: string;
}

export interface FieldErrorProps extends HTMLAttributes<HTMLParagraphElement> {
  /** Accepts RHF FieldError(s) or any object exposing a `message` string. */
  errors?: ReadonlyArray<FieldErrorIssue | undefined> | undefined;
}

export const FieldError = forwardRef<HTMLParagraphElement, FieldErrorProps>(
  ({ className, errors, children, ...props }, ref) => {
    const messages = (errors ?? [])
      .map((e) => (e && typeof e.message === "string" ? e.message : null))
      .filter((m): m is string => m !== null);

    if (children === undefined && messages.length === 0) return null;

    return (
      <p
        ref={ref}
        data-slot="field-error"
        role="alert"
        className={cn("text-sm font-medium text-destructive", className)}
        {...props}
      >
        {children ?? messages.join(" ")}
      </p>
    );
  },
);
FieldError.displayName = "FieldError";

// ---------- FieldSet + FieldLegend ----------------------------------------

export const FieldSet = forwardRef<HTMLFieldSetElement, HTMLAttributes<HTMLFieldSetElement>>(
  ({ className, ...props }, ref) => (
    <fieldset
      ref={ref}
      data-slot="field-set"
      className={cn("flex flex-col gap-4 border-0 p-0", className)}
      {...props}
    />
  ),
);
FieldSet.displayName = "FieldSet";

export const FieldLegend = forwardRef<HTMLLegendElement, HTMLAttributes<HTMLLegendElement>>(
  ({ className, ...props }, ref) => (
    <legend
      ref={ref}
      data-slot="field-legend"
      className={cn("text-base font-semibold leading-none text-foreground", className)}
      {...props}
    />
  ),
);
FieldLegend.displayName = "FieldLegend";

// ---------- FieldSeparator + FieldContent ---------------------------------

export const FieldSeparator = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      data-slot="field-separator"
      role="separator"
      className={cn("my-2 h-px w-full bg-border", className)}
      {...props}
    />
  ),
);
FieldSeparator.displayName = "FieldSeparator";

export const FieldContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      data-slot="field-content"
      className={cn("flex flex-col gap-1", className)}
      {...props}
    />
  ),
);
FieldContent.displayName = "FieldContent";
