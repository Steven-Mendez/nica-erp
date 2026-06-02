// Empresa fiscal-settings editor — four-section form rendered at
// /empresa/settings. Prefills from `useTenantQuery(activeId)`, gates
// the submit button on the `tenant.update` permission, and routes
// 422 / 409 backend errors through both the per-field error setter
// and the top-of-form FormErrorAlert. Spanish copy throughout.

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { Controller, useForm, type UseFormReturn } from "react-hook-form";
import { useHasPermission } from "@/api/useHasPermission";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { FormErrorAlert } from "@/components/form/form-error-alert";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { ProblemDetail } from "@/api/errors";
import {
  DEPARTAMENTOS,
  isValidMunicipio,
  municipiosOf,
} from "../data/nicaragua-geography";
import {
  EMPRESA_FISCAL_REGIMEN_LABELS,
  empresaFiscalSettingsSchema,
  type EmpresaFiscalSettingsValues,
} from "../schemas/empresa-fiscal-settings";
import { useUpdateActiveTenantMutation } from "../api/hooks";
import type { Tenant, UpdateTenantInput } from "../api/endpoints";

// --- RUC masking helpers --------------------------------------------------

/**
 * Force a free-form string into the ``NNN-NNNNNN-NNNNN`` mask. Used by
 * the input's onChange so the operator can paste either form and the
 * canonical version shows up in the field. The 14th character may be
 * alphabetic (DGI check digit) so we leave letters as-is.
 */
export function maskRuc(raw: string): string {
  const cleaned = raw.toUpperCase().replace(/[^0-9A-Z]/g, "");
  const a = cleaned.slice(0, 3);
  const b = cleaned.slice(3, 9);
  const c = cleaned.slice(9, 14);
  if (cleaned.length <= 3) return a;
  if (cleaned.length <= 9) return `${a}-${b}`;
  return `${a}-${b}-${c}`;
}

/**
 * Force a phone string into the ``+505 NNNN-NNNN`` mask. Backend's
 * FiscalPhone VO matches this exact shape.
 */
export function maskPhone(raw: string): string {
  const digits = raw.replace(/\D/g, "").replace(/^505/, "").slice(0, 8);
  if (digits.length === 0) return "";
  if (digits.length <= 4) return `+505 ${digits}`;
  return `+505 ${digits.slice(0, 4)}-${digits.slice(4)}`;
}

// --- 422 problem-detail → RHF setError ------------------------------------

/**
 * Walks an `ApiError`'s 422 problem-detail body and pins each pointer
 * to its RHF field. Unmapped pointers bubble up via the return value
 * so the caller can surface a form-level alert.
 */
export function mapApiProblemToFormErrors(
  form: UseFormReturn<EmpresaFiscalSettingsValues>,
  problem: ProblemDetail,
): { unmappedCount: number } {
  if (!Array.isArray(problem.errors)) return { unmappedCount: 0 };
  let unmapped = 0;
  for (const issue of problem.errors) {
    const path = pointerToField(issue.pointer);
    if (path === null) {
      unmapped += 1;
      continue;
    }
    form.setError(path, { type: "server", message: issue.message });
  }
  return { unmappedCount: unmapped };
}

const POINTER_TO_FIELD: Record<string, keyof EmpresaFiscalSettingsValues> = {
  "/ruc": "ruc",
  "/regime": "regimen",
  "/departamento": "departamento",
  "/municipality": "municipio",
  "/fiscal_address": "direccion",
  "/fiscal_email": "correo_fiscal",
  "/fiscal_phone": "telefono_fiscal",
  "/authorization_dgi/number": "resolucion_dgi",
  "/authorization_dgi/valid_from": "vigencia_inicio",
  "/authorization_dgi/valid_to": "vigencia_vencimiento",
};

function pointerToField(
  pointer: string,
): keyof EmpresaFiscalSettingsValues | null {
  return POINTER_TO_FIELD[pointer] ?? null;
}

// --- Form -----------------------------------------------------------------

function tenantToFormValues(tenant: Tenant): EmpresaFiscalSettingsValues {
  return {
    ruc: tenant.ruc ?? "",
    regimen:
      tenant.regime === "general" ||
      tenant.regime === "cuota_fija" ||
      tenant.regime === "pequeno_contribuyente"
        ? tenant.regime
        : "general",
    retenedor: tenant.is_withholder,
    departamento: tenant.departamento ?? "",
    municipio: tenant.municipality ?? "",
    direccion: tenant.fiscal_address ?? "",
    resolucion_dgi: tenant.authorization_dgi?.number ?? "",
    vigencia_inicio: tenant.authorization_dgi?.valid_from ?? "",
    vigencia_vencimiento: tenant.authorization_dgi?.valid_to ?? "",
    correo_fiscal: tenant.fiscal_email ?? "",
    telefono_fiscal: tenant.fiscal_phone ?? "",
  };
}

function formValuesToUpdateInput(
  values: EmpresaFiscalSettingsValues,
): UpdateTenantInput {
  return {
    ruc: values.ruc,
    regime: values.regimen,
    departamento: values.departamento,
    municipality: values.municipio,
    fiscal_address: values.direccion,
    fiscal_email: values.correo_fiscal,
    fiscal_phone: values.telefono_fiscal,
    is_withholder: values.retenedor,
    authorization_dgi: {
      number: values.resolucion_dgi,
      valid_from: values.vigencia_inicio,
      valid_to: values.vigencia_vencimiento,
    },
  };
}

interface EmpresaFiscalSettingsFormProps {
  tenant: Tenant;
}

const RUC_COLLISION_CODE = "tenants.ruc_collision";

export function EmpresaFiscalSettingsForm({ tenant }: EmpresaFiscalSettingsFormProps) {
  const canEdit = useHasPermission("tenant.update");
  const mutation = useUpdateActiveTenantMutation();
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const initialValues = useMemo(() => tenantToFormValues(tenant), [tenant]);

  const form = useForm<EmpresaFiscalSettingsValues>({
    resolver: zodResolver(empresaFiscalSettingsSchema),
    defaultValues: initialValues,
    mode: "onSubmit",
    reValidateMode: "onChange",
  });

  // Re-prefill if the tenant payload changes underneath (e.g. cache
  // gets a fresh /v1/tenants/{id} response after a sibling save).
  useEffect(() => {
    form.reset(initialValues);
  }, [initialValues, form]);

  const departamento = form.watch("departamento");

  // When the operator changes departamento, clear municipio if the
  // previous value is no longer valid under the new departamento.
  useEffect(() => {
    const current = form.getValues("municipio");
    if (current === "") return;
    if (departamento && !isValidMunicipio(departamento, current)) {
      form.setValue("municipio", "", { shouldValidate: false });
    }
  }, [departamento, form]);

  const onSubmit = (values: EmpresaFiscalSettingsValues): void => {
    mutation.mutate(formValuesToUpdateInput(values), {
      onSuccess: () => {
        setSavedAt(Date.now());
      },
      onError: (err) => {
        const apiError = err as { status?: number; detail?: ProblemDetail };
        const detail = apiError.detail;
        if (apiError.status === 422 && detail !== undefined) {
          mapApiProblemToFormErrors(form, detail);
        }
        // 409 RUC collision is handled at render time via the
        // FormErrorAlert; no setError on the ruc field per the spec.
      },
    });
  };

  const formError = mutation.error;
  const isRucCollision =
    (formError as { detail?: ProblemDetail } | null)?.detail?.code ===
      RUC_COLLISION_CODE ||
    ((formError as { status?: number } | null)?.status === 409 &&
      (formError as { detail?: ProblemDetail } | null)?.detail?.code !==
        undefined);

  if (!canEdit) {
    return <ReadOnlyFiscalSettings tenant={tenant} />;
  }

  return (
    <form
      onSubmit={form.handleSubmit(onSubmit)}
      className="mx-auto flex max-w-3xl flex-col gap-6 py-8"
      noValidate
    >
      <div>
        <h1 className="text-2xl font-semibold">Configuración de la empresa</h1>
        <p className="text-sm text-muted-foreground">
          Datos fiscales que aparecen en cada factura y reporte DGI.
        </p>
      </div>

      {isRucCollision ? (
        <Alert role="alert" variant="destructive">
          <AlertDescription>
            Este RUC ya está registrado en otra empresa.
          </AlertDescription>
        </Alert>
      ) : (
        <FormErrorAlert error={mutation.error} />
      )}

      {savedAt !== null && !mutation.isPending && !mutation.isError ? (
        <Alert variant="success">
          <AlertDescription>Datos fiscales guardados.</AlertDescription>
        </Alert>
      ) : null}

      {/* --- Identificación fiscal -------------------------------- */}
      <Section title="Identificación fiscal">
        <Controller
          name="ruc"
          control={form.control}
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="ruc">RUC</FieldLabel>
              <Input
                {...field}
                id="ruc"
                placeholder="J03-100000-00010"
                aria-invalid={fieldState.invalid}
                onChange={(e) => field.onChange(maskRuc(e.target.value))}
              />
              {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
            </Field>
          )}
        />
        <Controller
          name="regimen"
          control={form.control}
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="regimen">Régimen fiscal</FieldLabel>
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="regimen" aria-invalid={fieldState.invalid}>
                  <SelectValue placeholder="Selecciona un régimen" />
                </SelectTrigger>
                <SelectContent>
                  {(Object.keys(EMPRESA_FISCAL_REGIMEN_LABELS) as Array<
                    keyof typeof EMPRESA_FISCAL_REGIMEN_LABELS
                  >).map((key) => (
                    <SelectItem key={key} value={key}>
                      {EMPRESA_FISCAL_REGIMEN_LABELS[key]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
            </Field>
          )}
        />
        <Controller
          name="retenedor"
          control={form.control}
          render={({ field }) => (
            <Field>
              <label className="flex items-center gap-3 text-sm">
                <Switch
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  aria-label="¿Es agente retenedor?"
                />
                <span>¿Es agente retenedor?</span>
              </label>
            </Field>
          )}
        />
      </Section>

      {/* --- Dirección fiscal ------------------------------------- */}
      <Section title="Dirección fiscal">
        <Controller
          name="departamento"
          control={form.control}
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="departamento">Departamento</FieldLabel>
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="departamento" aria-invalid={fieldState.invalid}>
                  <SelectValue placeholder="Selecciona un departamento" />
                </SelectTrigger>
                <SelectContent>
                  {DEPARTAMENTOS.map((d) => (
                    <SelectItem key={d.name} value={d.name}>
                      {d.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
            </Field>
          )}
        />
        <Controller
          name="municipio"
          control={form.control}
          render={({ field, fieldState }) => {
            const options = departamento ? municipiosOf(departamento) : [];
            return (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel htmlFor="municipio">Municipio</FieldLabel>
                <Select
                  value={field.value}
                  onValueChange={field.onChange}
                  disabled={!departamento}
                >
                  <SelectTrigger id="municipio" aria-invalid={fieldState.invalid}>
                    <SelectValue
                      placeholder={
                        departamento
                          ? "Selecciona un municipio"
                          : "Primero elige un departamento"
                      }
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {options.map((m) => (
                      <SelectItem key={m} value={m}>
                        {m}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
              </Field>
            );
          }}
        />
        <Controller
          name="direccion"
          control={form.control}
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="direccion">Dirección</FieldLabel>
              <Textarea
                {...field}
                id="direccion"
                rows={3}
                placeholder="Calle, número, barrio, referencias…"
                aria-invalid={fieldState.invalid}
              />
              {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
            </Field>
          )}
        />
      </Section>

      {/* --- Vigencia DGI ----------------------------------------- */}
      <Section title="Vigencia DGI">
        <Controller
          name="resolucion_dgi"
          control={form.control}
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="resolucion_dgi">Resolución DGI</FieldLabel>
              <Input
                {...field}
                id="resolucion_dgi"
                placeholder="A-001"
                aria-invalid={fieldState.invalid}
              />
              {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
            </Field>
          )}
        />
        <div className="grid gap-4 md:grid-cols-2">
          <Controller
            name="vigencia_inicio"
            control={form.control}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel htmlFor="vigencia_inicio">Inicio de vigencia</FieldLabel>
                <Input
                  {...field}
                  id="vigencia_inicio"
                  type="date"
                  aria-invalid={fieldState.invalid}
                />
                {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
              </Field>
            )}
          />
          <Controller
            name="vigencia_vencimiento"
            control={form.control}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel htmlFor="vigencia_vencimiento">Vencimiento</FieldLabel>
                <Input
                  {...field}
                  id="vigencia_vencimiento"
                  type="date"
                  aria-invalid={fieldState.invalid}
                />
                {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
              </Field>
            )}
          />
        </div>
      </Section>

      {/* --- Contacto fiscal -------------------------------------- */}
      <Section title="Contacto fiscal">
        <Controller
          name="correo_fiscal"
          control={form.control}
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="correo_fiscal">Correo</FieldLabel>
              <Input
                {...field}
                id="correo_fiscal"
                type="email"
                autoComplete="email"
                placeholder="facturacion@miempresa.ni"
                aria-invalid={fieldState.invalid}
              />
              {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
            </Field>
          )}
        />
        <Controller
          name="telefono_fiscal"
          control={form.control}
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="telefono_fiscal">Teléfono</FieldLabel>
              <Input
                {...field}
                id="telefono_fiscal"
                type="tel"
                placeholder="+505 8888-8888"
                aria-invalid={fieldState.invalid}
                onChange={(e) => field.onChange(maskPhone(e.target.value))}
              />
              {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
            </Field>
          )}
        />
      </Section>

      <div className="flex justify-end">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Guardando…" : "Guardar cambios"}
        </Button>
      </div>
    </form>
  );
}

// --- Section helper -------------------------------------------------------

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <FieldGroup>{children}</FieldGroup>
      </CardContent>
    </Card>
  );
}

// --- Read-only branch (no tenant.update permission) -----------------------

function ReadOnlyFiscalSettings({ tenant }: { tenant: Tenant }) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 py-8">
      <div>
        <h1 className="text-2xl font-semibold">Configuración de la empresa</h1>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Permiso requerido</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Solo el propietario o administrador de la empresa puede editar los
          datos fiscales.
        </CardContent>
      </Card>
      <Card>
        <CardContent className="grid gap-3 py-4 text-sm">
          <ReadRow label="RUC" value={tenant.ruc} />
          <ReadRow label="Régimen" value={tenant.regime} />
          <ReadRow label="Municipio" value={tenant.municipality} />
          <ReadRow label="Dirección" value={tenant.fiscal_address} />
        </CardContent>
      </Card>
    </div>
  );
}

function ReadRow({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-2">
      <span className="font-medium">{label}</span>
      <span className="text-muted-foreground">{value ?? "—"}</span>
    </div>
  );
}
