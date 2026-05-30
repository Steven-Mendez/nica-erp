// /empresa/settings — placeholder for the fiscal-data editor.
// Per ADR-0034, tenant creation accepts only the empresa name; the
// operator fills the fiscal fields from this screen, which a
// follow-up sprint will wire up. The `useUpdateTenantMutation`
// hook is in place; the form is not.

import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function EmpresaConfiguracionRoute() {
  useDocumentTitle("Configuración de la empresa");
  return (
    <AppShell>
      <div className="mx-auto max-w-xl py-10">
        <Card>
          <CardHeader>
            <CardTitle>Configuración de la empresa</CardTitle>
            <CardDescription>
              Próximamente — esta pantalla permitirá editar los datos fiscales de tu empresa.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Aquí completarás el RUC, régimen, autorización DGI y dirección fiscal.
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
