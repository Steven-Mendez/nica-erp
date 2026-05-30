// apps/web/src/routes/welcome.tsx
//
// First-login screen — captures `display_name` and `timezone`. The
// timezone is pre-selected with the browser's IANA value. `locale`
// is intentionally NOT asked (deferred per ADR-0033). On submit the
// SPA PATCHes /v1/me and navigates to the next guard step.

import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "@tanstack/react-router";
import { Check, ChevronsUpDown } from "lucide-react";
import { useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useUpdateMeMutation } from "@/features/auth/api/hooks";
import { cn } from "@/lib/utils";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

const welcomeSchema = z.object({
  display_name: z.string().min(2, "Mínimo 2 caracteres").max(100, "Máximo 100 caracteres"),
  timezone: z.string().min(1, "Selecciona una zona horaria"),
});

type WelcomeValues = z.infer<typeof welcomeSchema>;

/**
 * Returns the IANA timezones the browser knows about. Falls back to
 * a short curated list when `Intl.supportedValuesOf` is unavailable
 * (older Safari versions).
 */
function listTimezones(): string[] {
  const intlAny = Intl as unknown as {
    supportedValuesOf?: (key: string) => string[];
  };
  if (typeof intlAny.supportedValuesOf === "function") {
    return intlAny.supportedValuesOf("timeZone");
  }
  return [
    "America/Managua",
    "America/Mexico_City",
    "America/Guatemala",
    "America/El_Salvador",
    "America/Tegucigalpa",
    "America/Costa_Rica",
    "America/Panama",
    "America/Santo_Domingo",
    "Europe/Madrid",
    "America/New_York",
    "America/Los_Angeles",
    "UTC",
  ];
}

function detectBrowserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

interface TimezoneComboboxProps {
  id: string;
  value: string;
  onChange: (value: string) => void;
  onBlur: () => void;
  options: string[];
  invalid: boolean;
}

function TimezoneCombobox({
  id,
  value,
  onChange,
  onBlur,
  options,
  invalid,
}: TimezoneComboboxProps) {
  const [open, setOpen] = useState(false);
  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) onBlur();
      }}
    >
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-invalid={invalid}
          className={cn(
            "w-full justify-between font-normal",
            value === "" && "text-muted-foreground",
          )}
        >
          {value === "" ? "Selecciona una zona horaria" : value}
          <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
        <Command>
          <CommandInput placeholder="Buscar zona horaria..." />
          <CommandList>
            <CommandEmpty>Sin resultados.</CommandEmpty>
            <CommandGroup>
              {options.map((tz) => (
                <CommandItem
                  key={tz}
                  value={tz}
                  onSelect={(selected) => {
                    onChange(selected);
                    setOpen(false);
                  }}
                >
                  <Check
                    className={cn("mr-2 size-4", value === tz ? "opacity-100" : "opacity-0")}
                  />
                  {tz}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export function WelcomeRoute() {
  useDocumentTitle("Bienvenido");
  const navigate = useNavigate();
  const mutation = useUpdateMeMutation();
  const timezones = useMemo(() => listTimezones(), []);
  const form = useForm<WelcomeValues>({
    resolver: zodResolver(welcomeSchema),
    defaultValues: { display_name: "", timezone: detectBrowserTimezone() },
    mode: "onSubmit",
    reValidateMode: "onChange",
  });

  const onSubmit = (values: WelcomeValues): void => {
    mutation.mutate(
      { display_name: values.display_name, timezone: values.timezone },
      {
        onSuccess: () => {
          void navigate({ to: "/" });
        },
      },
    );
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Bienvenido a Nica ERP</CardTitle>
          <CardDescription>
            Cuéntanos tu nombre y zona horaria para configurar tu cuenta.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
            <FieldGroup>
              <Controller
                name="display_name"
                control={form.control}
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor="display_name">Nombre</FieldLabel>
                    <Input
                      {...field}
                      id="display_name"
                      autoComplete="name"
                      placeholder="Ada Lovelace"
                      required
                      aria-invalid={fieldState.invalid}
                    />
                    {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
                  </Field>
                )}
              />
              <Controller
                name="timezone"
                control={form.control}
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor="timezone">Zona horaria</FieldLabel>
                    <TimezoneCombobox
                      id="timezone"
                      value={field.value}
                      onChange={field.onChange}
                      onBlur={field.onBlur}
                      options={timezones}
                      invalid={fieldState.invalid}
                    />
                    {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
                  </Field>
                )}
              />
              {mutation.isError ? (
                <Alert variant="destructive">
                  <AlertDescription>
                    No se pudo guardar tu perfil. Intenta de nuevo.
                  </AlertDescription>
                </Alert>
              ) : null}
              <Button type="submit" className="w-full" disabled={mutation.isPending}>
                {mutation.isPending ? "Guardando..." : "Continuar"}
              </Button>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
