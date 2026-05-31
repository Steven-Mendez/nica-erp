// apps/web/src/routes/tenants/new.tsx
//
// Four-step skippable wizard for empresa creation. Per ADR-0034,
// only `name` is strictly required at creation time; every other
// fiscal field is optional. The wizard offers two paths on every
// step:
//
//   • "Continuar"      → advance to the next step (or, on the
//                        last step, submit the full payload).
//   • "Saltar y crear" → submit immediately with whatever has been
//                        captured so far.
//
// On step 1 "Saltar y crear" is disabled until the empresa name
// is non-empty. On steps 2-4 it is always enabled.
//
// The backend (CreateTenantRequest) coerces empty strings / empty
// objects to NULL on its side, so the wizard can freely send the
// raw form values without pre-stripping.

import { useState, type ComponentType, type SVGProps } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "@tanstack/react-router";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { ArrowLeft, Building2, Check, Info, MapPin, ReceiptText, ShieldCheck } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { DatePicker } from "@/components/ui/date-picker";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { ApiError } from "@/features/tenants/api/endpoints";
import { useCreateTenantMutation, useSwitchTenantMutation } from "@/features/tenants/api/hooks";
import { MUNICIPALITIES } from "@/features/tenants/municipalities";
import { createTenantSchema, type CreateTenantValues } from "@/features/tenants/schemas";
import { useDocumentTitle } from "@/lib/useDocumentTitle";
import { getRefreshToken } from "@/api/tokenStore";
import { BrandLayout } from "@/components/brand-header";

type StepKey = "identity" | "regime" | "dgi" | "address";
type StepIcon = ComponentType<SVGProps<SVGSVGElement>>;
type Step = {
  key: StepKey;
  title: string;
  description: string;
  icon: StepIcon;
};

const STEPS: Step[] = [
  {
    key: "identity",
    title: "Identidad",
    description: "Nombre y RUC de tu empresa.",
    icon: Building2,
  },
  {
    key: "regime",
    title: "Régimen fiscal",
    description: "Régimen, municipio y condición de retenedor.",
    icon: ReceiptText,
  },
  {
    key: "dgi",
    title: "Autorización DGI",
    description: "Datos de la autorización emitida por la DGI.",
    icon: ShieldCheck,
  },
  {
    key: "address",
    title: "Dirección y resumen",
    description: "Dirección fiscal y revisión final.",
    icon: MapPin,
  },
];

const FIELD_LABELS: Record<string, string> = {
  name: "Nombre",
  ruc: "RUC",
  regime: "Régimen",
  municipality: "Municipio",
  "authorization_dgi.number": "Número DGI",
  "authorization_dgi.valid_from": "Vigencia desde",
  "authorization_dgi.valid_to": "Vigencia hasta",
  fiscal_address: "Dirección fiscal",
  is_withholder: "Es retenedor",
};

const FALLBACK_ERROR = "No se pudo crear la empresa. Revisa los datos e intenta de nuevo.";

const formatApiError = (err: Error): string => {
  if (!(err instanceof ApiError)) return err.message || FALLBACK_ERROR;
  const detail = err.detail as {
    detail?: Array<{ loc?: unknown[]; msg?: string }> | string;
  } | null;
  if (typeof detail?.detail === "string" && detail.detail !== "") {
    return detail.detail;
  }
  const first = Array.isArray(detail?.detail) ? detail.detail[0] : undefined;
  if (first === undefined) return FALLBACK_ERROR;
  const loc = Array.isArray(first.loc) ? first.loc.slice(1).map(String).join(".") : "";
  const label = FIELD_LABELS[loc] ?? loc;
  const msg = typeof first.msg === "string" && first.msg !== "" ? first.msg : FALLBACK_ERROR;
  return label === "" ? msg : `${label}: ${msg}`;
};

const InfoTip = ({ text }: { text: string }) => (
  <Tooltip>
    <TooltipTrigger asChild>
      <button
        type="button"
        className="inline-flex items-center justify-center text-muted-foreground hover:text-foreground"
        aria-label="Más información"
      >
        <Info className="size-3.5" />
      </button>
    </TooltipTrigger>
    <TooltipContent side="top" className="max-w-xs text-xs">
      {text}
    </TooltipContent>
  </Tooltip>
);

const formatReviewDate = (iso: string | undefined): string => {
  if (iso === undefined || iso === "") return "—";
  const parts = iso.split("-");
  if (parts.length !== 3) return iso;
  const [y, m, d] = parts.map(Number) as [number, number, number];
  if (Number.isNaN(y) || Number.isNaN(m) || Number.isNaN(d)) return iso;
  return format(new Date(y, m - 1, d), "dd MMM yyyy", { locale: es });
};

type CreateTenantBody = {
  name: string;
  is_withholder: boolean;
  ruc?: string | null;
  regime?: "general" | "simplified" | null;
  municipality?: string | null;
  authorization_dgi?: { number: string; valid_from: string; valid_to: string } | null;
  fiscal_address?: string | null;
};

const buildPayload = (values: CreateTenantValues): CreateTenantBody => {
  const out: CreateTenantBody = {
    name: values.name,
    is_withholder: values.is_withholder ?? false,
  };
  if (values.ruc !== undefined && values.ruc !== "") out.ruc = values.ruc;
  if (values.regime !== undefined) out.regime = values.regime;
  if (values.municipality !== undefined) out.municipality = values.municipality;
  if (values.fiscal_address !== undefined && values.fiscal_address !== "") {
    out.fiscal_address = values.fiscal_address;
  }
  const dgi = values.authorization_dgi;
  if (
    dgi !== undefined &&
    typeof dgi.number === "string" &&
    dgi.number !== "" &&
    typeof dgi.valid_from === "string" &&
    dgi.valid_from !== "" &&
    typeof dgi.valid_to === "string" &&
    dgi.valid_to !== ""
  ) {
    out.authorization_dgi = {
      number: dgi.number,
      valid_from: dgi.valid_from,
      valid_to: dgi.valid_to,
    };
  }
  return out;
};

type HorizontalStepsProps = { steps: Step[]; current: number };

const HorizontalSteps = ({ steps, current }: HorizontalStepsProps) => {
  const currentStep = steps[current];
  return (
    <div className="space-y-2">
      <ol className="flex items-center gap-2">
        {steps.map((s, i) => {
          const isCurrent = i === current;
          const isDone = i < current;
          const isLast = i === steps.length - 1;
          return (
            <li key={s.key} className="flex flex-1 items-center gap-2 last:flex-none">
              <span
                aria-current={isCurrent ? "step" : undefined}
                aria-label={s.title}
                className={cn(
                  "flex size-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold transition-colors",
                  isDone && "border-primary bg-primary text-primary-foreground",
                  isCurrent && "border-primary bg-background text-primary",
                  !isDone && !isCurrent && "border-border bg-background text-muted-foreground",
                )}
              >
                {isDone ? <Check className="size-3.5" aria-hidden="true" /> : i + 1}
              </span>
              {!isLast ? (
                <span
                  aria-hidden="true"
                  className={cn(
                    "h-px flex-1 transition-colors",
                    isDone ? "bg-primary/60" : "bg-border",
                  )}
                />
              ) : null}
            </li>
          );
        })}
      </ol>
      {currentStep !== undefined ? (
        <p className="text-xs font-medium text-foreground">{currentStep.title}</p>
      ) : null}
    </div>
  );
};

type VerticalStepsProps = { steps: Step[]; current: number };

const VerticalSteps = ({ steps, current }: VerticalStepsProps) => (
  <ol className="relative space-y-1">
    {steps.map((s, i) => {
      const isCurrent = i === current;
      const isDone = i < current;
      const Icon = s.icon;
      const isLast = i === steps.length - 1;
      return (
        <li key={s.key} className="relative">
          {!isLast ? (
            <span
              aria-hidden="true"
              className={cn(
                "absolute left-[1.625rem] top-11 h-[calc(100%-1.75rem)] w-px",
                isDone ? "bg-primary/70" : "bg-border",
              )}
            />
          ) : null}
          <div
            aria-current={isCurrent ? "step" : undefined}
            className={cn(
              "relative flex items-start gap-3 rounded-md px-2 py-2 transition-colors",
              isCurrent && "bg-muted/60",
            )}
          >
            <span
              className={cn(
                "z-10 flex size-9 shrink-0 items-center justify-center rounded-full border text-xs font-semibold transition-colors",
                isDone && "border-primary bg-primary text-primary-foreground",
                isCurrent && "border-primary bg-background text-primary shadow-xs",
                !isDone && !isCurrent && "border-border bg-background text-muted-foreground",
              )}
            >
              {isDone ? (
                <Check className="size-4" aria-hidden="true" />
              ) : (
                <Icon className="size-4" aria-hidden="true" />
              )}
            </span>
            <div className="flex min-w-0 flex-col leading-tight">
              <span
                className={cn(
                  "text-xs uppercase tracking-wide",
                  isCurrent ? "text-primary" : "text-muted-foreground/70",
                )}
              >
                Paso {i + 1}
              </span>
              <span
                className={cn(
                  "truncate text-sm",
                  isCurrent && "font-semibold text-foreground",
                  isDone && "text-muted-foreground",
                  !isDone && !isCurrent && "text-muted-foreground",
                )}
              >
                {s.title}
              </span>
            </div>
          </div>
        </li>
      );
    })}
  </ol>
);

export function TenantsNewRoute() {
  useDocumentTitle("Crear empresa");
  const navigate = useNavigate();
  const createMut = useCreateTenantMutation();
  const switchMut = useSwitchTenantMutation();
  const [stepIndex, setStepIndex] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [attemptedSteps, setAttemptedSteps] = useState<Set<StepKey>>(new Set());

  const form = useForm<CreateTenantValues>({
    resolver: zodResolver(createTenantSchema),
    mode: "onTouched",
    reValidateMode: "onChange",
    defaultValues: {
      name: "",
      is_withholder: false,
    },
  });
  const {
    control,
    handleSubmit,
    trigger,
    getValues,
    watch,
    formState: { errors, touchedFields, isSubmitted },
  } = form;

  const step = STEPS[stepIndex] ?? STEPS[0]!;
  const StepIcon = step.icon;
  const isFirst = stepIndex === 0;
  const isLast = stepIndex === STEPS.length - 1;
  const stepAttempted = attemptedSteps.has(step.key);
  const showError = (touched: boolean | undefined): boolean =>
    isSubmitted || stepAttempted || touched === true;
  const progressValue = ((stepIndex + 1) / STEPS.length) * 100;

  const nameValue = watch("name");
  const canSkipAndCreate = (nameValue ?? "").trim().length > 0;

  const goNext = async (): Promise<void> => {
    const ok = await trigger();
    if (!ok) {
      setAttemptedSteps((s) => new Set(s).add(step.key));
      return;
    }
    setStepIndex((i) => Math.min(i + 1, STEPS.length - 1));
  };

  const goBack = (): void => {
    setStepIndex((i) => Math.max(i - 1, 0));
  };

  const onSubmit = (values: CreateTenantValues): void => {
    setErrorMsg(null);
    createMut.mutate(buildPayload(values), {
      onSuccess: (tenant) => {
        const refresh = getRefreshToken();
        if (refresh === null) {
          void navigate({ to: "/" });
          return;
        }
        switchMut.mutate(
          { tenantId: tenant.id, input: { refresh_token: refresh } },
          {
            onSuccess: () => {
              void navigate({ to: "/dashboard" });
            },
            onError: () => {
              void navigate({ to: "/tenants" });
            },
          },
        );
      },
      onError: (err) => {
        setErrorMsg(formatApiError(err));
      },
    });
  };

  const pending = createMut.isPending || switchMut.isPending;

  const skipAndCreate = async (): Promise<void> => {
    const ok = await trigger("name");
    if (!ok) return;
    onSubmit(getValues());
  };

  const skipTitle = canSkipAndCreate
    ? "Crea la empresa con lo capturado hasta ahora. Podés completar el resto después."
    : "Ingresa el nombre primero";

  return (
    <BrandLayout>
      <TooltipProvider delayDuration={250}>
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-5 px-4 py-6 sm:gap-6 sm:py-10">
          <div className="flex items-center justify-between">
            <Link
              to="/tenants"
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <ArrowLeft className="size-4" aria-hidden="true" />
              Volver a empresas
            </Link>
            <span className="text-xs text-muted-foreground">
              Paso {stepIndex + 1} de {STEPS.length}
            </span>
          </div>

          {/* Mobile-only horizontal stepper */}
          <div className="space-y-2 md:hidden">
            <HorizontalSteps steps={STEPS} current={stepIndex} />
            <Progress value={progressValue} aria-label="Progreso del asistente" />
          </div>

          <div className="grid items-stretch gap-5 md:grid-cols-[15rem_1fr] md:gap-6">
            {/* Desktop-only left rail */}
            <aside className="hidden md:flex md:flex-col">
              <div className="flex h-full flex-col gap-5 rounded-lg bg-card p-5 text-card-foreground ring-1 ring-foreground/10">
                <div className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Asistente
                  </span>
                  <Progress value={progressValue} aria-label="Progreso del asistente" />
                </div>
                <VerticalSteps steps={STEPS} current={stepIndex} />
              </div>
            </aside>

            <Card className="shadow-xs">
              <CardHeader className="gap-3">
                <div className="flex items-start gap-3">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-lg border bg-background text-primary shadow-xs">
                    <StepIcon className="size-5" aria-hidden="true" />
                  </span>
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <CardTitle className="text-lg">{step.title}</CardTitle>
                      <Badge variant="secondary" className="text-[10px] uppercase tracking-wide">
                        {step.key === "identity" ? "Requerido" : "Opcional"}
                      </Badge>
                    </div>
                    <CardDescription>{step.description}</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <form onSubmit={handleSubmit(onSubmit)}>
                <CardContent className="space-y-6">
                  {step.key === "identity" ? (
                    <FieldGroup>
                      <Controller
                        name="name"
                        control={control}
                        render={({ field, fieldState }) => {
                          const invalid = showError(touchedFields.name) && fieldState.invalid;
                          return (
                            <Field data-invalid={invalid}>
                              <FieldLabel htmlFor="name">
                                Nombre{" "}
                                <span aria-hidden="true" className="ml-0.5 text-destructive">
                                  *
                                </span>
                              </FieldLabel>
                              <Input
                                {...field}
                                id="name"
                                placeholder="Nombre de tu empresa"
                                autoComplete="organization"
                                aria-invalid={invalid}
                              />
                              <FieldDescription>
                                Cómo aparecerá en facturas y reportes.
                              </FieldDescription>
                              {invalid ? <FieldError errors={[errors.name]} /> : null}
                            </Field>
                          );
                        }}
                      />
                      <Controller
                        name="ruc"
                        control={control}
                        render={({ field, fieldState }) => {
                          const invalid = showError(touchedFields.ruc) && fieldState.invalid;
                          return (
                            <Field data-invalid={invalid}>
                              <FieldLabel htmlFor="ruc">RUC</FieldLabel>
                              <Input
                                {...field}
                                value={field.value ?? ""}
                                id="ruc"
                                placeholder="0010101800010X"
                                inputMode="text"
                                autoCapitalize="characters"
                                spellCheck={false}
                                className="font-mono"
                                aria-invalid={invalid}
                              />
                              <FieldDescription>
                                13 dígitos seguidos de una letra mayúscula.
                              </FieldDescription>
                              {invalid ? <FieldError errors={[errors.ruc]} /> : null}
                            </Field>
                          );
                        }}
                      />
                    </FieldGroup>
                  ) : null}

                  {step.key === "regime" ? (
                    <FieldGroup>
                      <Controller
                        name="regime"
                        control={control}
                        render={({ field }) => (
                          <Field>
                            <FieldLabel htmlFor="regime" className="gap-1.5">
                              Régimen
                              <InfoTip text="General: factura IVA estándar. Simplificado: cuota fija mensual para pequeñas empresas." />
                            </FieldLabel>
                            <Select value={field.value ?? ""} onValueChange={field.onChange}>
                              <SelectTrigger id="regime" className="w-full">
                                <SelectValue placeholder="Selecciona un régimen" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="general">General</SelectItem>
                                <SelectItem value="simplified">Simplificado</SelectItem>
                              </SelectContent>
                            </Select>
                          </Field>
                        )}
                      />
                      <Controller
                        name="municipality"
                        control={control}
                        render={({ field }) => (
                          <Field>
                            <FieldLabel htmlFor="municipality" className="gap-1.5">
                              Municipio
                              <InfoTip text="Municipio fiscal de la empresa; debe pertenecer al catálogo aceptado por la DGI." />
                            </FieldLabel>
                            <Select value={field.value ?? ""} onValueChange={field.onChange}>
                              <SelectTrigger id="municipality" className="w-full">
                                <SelectValue placeholder="Selecciona un municipio" />
                              </SelectTrigger>
                              <SelectContent>
                                {MUNICIPALITIES.map((m) => (
                                  <SelectItem key={m} value={m}>
                                    {m}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </Field>
                        )}
                      />
                      <Field
                        orientation="horizontal"
                        className="rounded-md border bg-muted/30 px-3 py-2.5"
                      >
                        <Controller
                          name="is_withholder"
                          control={control}
                          render={({ field }) => (
                            <Checkbox
                              id="is_withholder"
                              checked={field.value === true}
                              onCheckedChange={(v) => field.onChange(v === true)}
                            />
                          )}
                        />
                        <Label htmlFor="is_withholder" className="text-sm font-normal">
                          Es retenedor
                        </Label>
                        <InfoTip text="Un retenedor IR es una empresa designada por la DGI para retener impuestos a sus proveedores en cada pago." />
                      </Field>
                    </FieldGroup>
                  ) : null}

                  {step.key === "dgi" ? (
                    <FieldGroup>
                      <Controller
                        name="authorization_dgi.number"
                        control={control}
                        render={({ field, fieldState }) => {
                          const invalid =
                            showError(touchedFields.authorization_dgi?.number) &&
                            fieldState.invalid;
                          return (
                            <Field data-invalid={invalid}>
                              <FieldLabel htmlFor="dgi_number" className="gap-1.5">
                                Número
                                <InfoTip text="Número de autorización de impresión emitido por la DGI para los rangos de comprobante fiscal." />
                              </FieldLabel>
                              <Input
                                {...field}
                                value={field.value ?? ""}
                                id="dgi_number"
                                className="font-mono"
                                aria-invalid={invalid}
                              />
                              {invalid ? (
                                <FieldError errors={[errors.authorization_dgi?.number]} />
                              ) : null}
                            </Field>
                          );
                        }}
                      />
                      <div className="grid gap-4 sm:grid-cols-2">
                        <Controller
                          name="authorization_dgi.valid_from"
                          control={control}
                          render={({ field, fieldState }) => (
                            <Field>
                              <FieldLabel htmlFor="valid_from">Válido desde</FieldLabel>
                              <DatePicker
                                id="valid_from"
                                value={field.value ?? ""}
                                onChange={field.onChange}
                                placeholder="Selecciona la fecha desde"
                                aria-invalid={fieldState.invalid}
                              />
                            </Field>
                          )}
                        />
                        <Controller
                          name="authorization_dgi.valid_to"
                          control={control}
                          render={({ field, fieldState }) => (
                            <Field>
                              <FieldLabel htmlFor="valid_to">Válido hasta</FieldLabel>
                              <DatePicker
                                id="valid_to"
                                value={field.value ?? ""}
                                onChange={field.onChange}
                                placeholder="Selecciona la fecha hasta"
                                aria-invalid={fieldState.invalid}
                              />
                            </Field>
                          )}
                        />
                      </div>
                    </FieldGroup>
                  ) : null}

                  {step.key === "address" ? (
                    <FieldGroup>
                      <Controller
                        name="fiscal_address"
                        control={control}
                        render={({ field, fieldState }) => {
                          const invalid =
                            showError(touchedFields.fiscal_address) && fieldState.invalid;
                          return (
                            <Field data-invalid={invalid}>
                              <FieldLabel htmlFor="fiscal_address">Dirección fiscal</FieldLabel>
                              <Input
                                {...field}
                                value={field.value ?? ""}
                                id="fiscal_address"
                                placeholder="Calle, número, barrio…"
                                aria-invalid={invalid}
                              />
                              {invalid ? <FieldError errors={[errors.fiscal_address]} /> : null}
                            </Field>
                          );
                        }}
                      />

                      <ReviewSummary
                        name={getValues("name")}
                        ruc={getValues("ruc")}
                        regime={getValues("regime")}
                        municipality={getValues("municipality")}
                        isWithholder={getValues("is_withholder") === true}
                        dgiNumber={getValues("authorization_dgi.number")}
                        validFrom={getValues("authorization_dgi.valid_from")}
                        validTo={getValues("authorization_dgi.valid_to")}
                        fiscalAddress={getValues("fiscal_address")}
                      />
                    </FieldGroup>
                  ) : null}

                  {errorMsg ? (
                    <Alert variant="destructive">
                      <AlertDescription>{errorMsg}</AlertDescription>
                    </Alert>
                  ) : null}
                </CardContent>
                <CardFooter className="flex flex-wrap items-center justify-between gap-2 pt-2">
                  <div className="flex gap-2">
                    {isFirst ? null : (
                      <Button type="button" variant="ghost" onClick={goBack} disabled={pending}>
                        <ArrowLeft className="size-4" aria-hidden="true" />
                        Atrás
                      </Button>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {isLast ? null : (
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => void skipAndCreate()}
                        disabled={!canSkipAndCreate || pending}
                        title={skipTitle}
                      >
                        Saltar y crear
                      </Button>
                    )}
                    {isLast ? (
                      <Button type="submit" disabled={pending || !canSkipAndCreate}>
                        {pending ? "Creando..." : "Crear empresa"}
                      </Button>
                    ) : (
                      <Button type="button" onClick={() => void goNext()} disabled={pending}>
                        Continuar
                      </Button>
                    )}
                  </div>
                </CardFooter>
              </form>
            </Card>
          </div>
        </div>
      </TooltipProvider>
    </BrandLayout>
  );
}

type ReviewSummaryProps = {
  name: string;
  ruc: string | undefined | null;
  regime: "general" | "simplified" | undefined | null;
  municipality: string | undefined | null;
  isWithholder: boolean;
  dgiNumber: string | undefined | null;
  validFrom: string | undefined | null;
  validTo: string | undefined | null;
  fiscalAddress: string | undefined | null;
};

function ReviewSummary(props: ReviewSummaryProps) {
  const regimeLabel =
    props.regime === "general" ? "General" : props.regime === "simplified" ? "Simplificado" : "—";

  return (
    <div className="space-y-4 rounded-lg border bg-muted/30 p-5">
      <div className="flex items-center gap-2">
        <Check className="size-4 text-primary" aria-hidden="true" />
        <h2 className="text-sm font-semibold">Revisión final</h2>
      </div>

      <FieldSet>
        <FieldLegend className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <Building2 className="size-3.5 text-muted-foreground" aria-hidden="true" />
          Identidad
        </FieldLegend>
        <dl className="grid gap-x-4 gap-y-2 sm:grid-cols-2">
          <ReviewRow label="Nombre" value={props.name || "—"} />
          <ReviewRow label="RUC" value={props.ruc ?? "—"} mono />
        </dl>
      </FieldSet>

      <FieldSet>
        <FieldLegend className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <ReceiptText className="size-3.5 text-muted-foreground" aria-hidden="true" />
          Régimen fiscal
        </FieldLegend>
        <dl className="grid gap-x-4 gap-y-2 sm:grid-cols-2">
          <ReviewRow label="Régimen" value={regimeLabel} />
          <ReviewRow label="Municipio" value={props.municipality ?? "—"} />
          <div className="space-y-0.5 sm:col-span-2">
            <dt className="text-xs text-muted-foreground">Retenedor</dt>
            <dd>
              <Badge variant={props.isWithholder ? "default" : "secondary"}>
                {props.isWithholder ? "Sí" : "No"}
              </Badge>
            </dd>
          </div>
        </dl>
      </FieldSet>

      <FieldSet>
        <FieldLegend className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <ShieldCheck className="size-3.5 text-muted-foreground" aria-hidden="true" />
          Autorización DGI
        </FieldLegend>
        <dl className="grid gap-x-4 gap-y-2 sm:grid-cols-2">
          <ReviewRow label="Número" value={props.dgiNumber || "—"} mono />
          <div className="space-y-0.5 sm:col-span-2">
            <dt className="text-xs text-muted-foreground">Vigencia</dt>
            <dd className="text-sm font-medium">
              {formatReviewDate(props.validFrom ?? undefined)}{" "}
              <span className="text-muted-foreground">→</span>{" "}
              {formatReviewDate(props.validTo ?? undefined)}
            </dd>
          </div>
        </dl>
      </FieldSet>

      <FieldSet>
        <FieldLegend className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <MapPin className="size-3.5 text-muted-foreground" aria-hidden="true" />
          Dirección
        </FieldLegend>
        <dl>
          <ReviewRow label="Dirección fiscal" value={props.fiscalAddress ?? "—"} />
        </dl>
      </FieldSet>
    </div>
  );
}

function ReviewRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn("text-sm font-medium", mono === true && "font-mono")}>{value}</dd>
    </div>
  );
}
