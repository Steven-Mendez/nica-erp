// Inline auth-error alert. The auth routes (/login, /confirm,
// /forgot-password, /reset-password) render this above the submit
// button whenever the mutation's `error` is non-null. Spanish copy
// is sourced from `messageForProblem` so the registry stays the
// single source of truth — unknown error shapes fall through to
// the generic copy and never leak the raw backend code into the UI.
//
// `role="alert"` + `aria-live="assertive"` are deliberate: form
// errors are interruptive, and screen-reader users need them
// announced as soon as the mutation settles, not after a tab
// re-focus.

import { AlertCircle } from "lucide-react";
import { messageForProblem } from "@/api/errors";
import { cn } from "@/lib/utils";

interface FormErrorAlertProps {
  error: unknown;
  className?: string;
}

export function FormErrorAlert({ error, className }: FormErrorAlertProps) {
  if (error === null || error === undefined) return null;
  const message = messageForProblem(error);
  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        "flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/5 px-3 py-2 text-sm text-destructive",
        className,
      )}
    >
      <AlertCircle className="size-4 shrink-0 translate-y-0.5" aria-hidden />
      <span>{message}</span>
    </div>
  );
}
