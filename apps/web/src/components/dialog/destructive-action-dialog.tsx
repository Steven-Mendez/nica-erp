// Wrapper around shadcn `<AlertDialog>` that codifies the empresa
// app's destructive-confirm pattern: the cancel button is the
// auto-focused default and is rendered first; the confirm button
// carries the destructive variant; both have Spanish-defaulted
// labels. The wrapper exists so feature code only needs to think
// about "what's the question, what's the irreversible action".
//
// `Escape` and clicking the overlay close the dialog without firing
// `onConfirm` (the underlying Radix primitive). The trigger element
// stays out of the wrapper so callers can place it wherever the
// destructive action lives (a row button, a dropdown menu item, etc).

import { AlertCircle } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface DestructiveActionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  /** Defaults to "Cancelar" if omitted. */
  cancelLabel?: string;
  /** Defaults to "Eliminar" if omitted. */
  confirmLabel?: string;
  /** Called once when the operator confirms the destructive action. */
  onConfirm: () => void;
  /** When true, disable both buttons (e.g. while a mutation is pending). */
  pending?: boolean;
}

export function DestructiveActionDialog({
  open,
  onOpenChange,
  title,
  description,
  cancelLabel = "Cancelar",
  confirmLabel = "Eliminar",
  onConfirm,
  pending = false,
}: DestructiveActionDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <AlertCircle className="size-5 text-destructive" aria-hidden />
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          {/* Cancel is rendered first AND auto-focused so the safer
              outcome is the default. The autoFocus prop is documented
              in radix-ui — focus moves to this element when the
              dialog opens. */}
          <AlertDialogCancel autoFocus disabled={pending}>
            {cancelLabel}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={pending}
            className={cn(buttonVariants({ variant: "destructive" }))}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
