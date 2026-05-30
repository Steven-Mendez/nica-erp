import { MailQuestion, Users } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useHasPermission } from "@/api/useHasPermission";
import { useMeQuery } from "@/features/auth/api/hooks";
import { InvitationsTable } from "@/features/tenants/components/InvitationsTable";
import { InviteMemberDialog } from "@/features/tenants/components/InviteMemberDialog";
import { MembersTable } from "@/features/tenants/components/MembersTable";
import { useInvitationsQuery, useMembersQuery } from "@/features/tenants/api/hooks";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function EmpresaUsuariosRoute() {
  useDocumentTitle("Usuarios");
  const me = useMeQuery();
  const tenantId = me.data?.active_tenant ?? "";
  const members = useMembersQuery(tenantId);
  const invitations = useInvitationsQuery(tenantId);
  const canInvite = useHasPermission("members:invite");
  const canRemove = useHasPermission("members:remove");
  const canUpdateRole = useHasPermission("members:update-role");

  const memberCount = members.data?.length ?? 0;
  const pendingCount = (invitations.data ?? []).filter((i) => i.status === "pending").length;

  return (
    <AppShell>
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
        <div className="flex flex-wrap items-start justify-between gap-3 px-4 lg:px-6">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Usuarios</h1>
            <p className="text-sm text-muted-foreground">
              Administra los miembros e invitaciones de tu empresa.
            </p>
          </div>
          {canInvite ? <InviteMemberDialog tenantId={tenantId} /> : null}
        </div>

        <div className="grid gap-4 px-4 sm:grid-cols-2 lg:px-6">
          <StatCard
            icon={<Users className="h-4 w-4" />}
            label="Miembros"
            value={memberCount}
            hint="Cuentas con acceso a la empresa"
          />
          <StatCard
            icon={<MailQuestion className="h-4 w-4" />}
            label="Invitaciones pendientes"
            value={pendingCount}
            hint="Aún no aceptadas"
          />
        </div>

        <div className="px-4 lg:px-6">
          <Card>
            <Tabs defaultValue="members" className="w-full">
              <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-1">
                  <CardTitle>Personas</CardTitle>
                  <CardDescription>
                    Miembros activos e invitaciones pendientes de esta empresa.
                  </CardDescription>
                </div>
                <TabsList>
                  <TabsTrigger value="members" className="gap-2">
                    Miembros
                    <Badge variant="secondary" className="px-1.5 py-0 text-[10px]">
                      {memberCount}
                    </Badge>
                  </TabsTrigger>
                  <TabsTrigger value="invitations" className="gap-2">
                    Invitaciones
                    <Badge
                      variant={pendingCount > 0 ? "warn" : "secondary"}
                      className="px-1.5 py-0 text-[10px]"
                    >
                      {pendingCount}
                    </Badge>
                  </TabsTrigger>
                </TabsList>
              </CardHeader>
              <CardContent>
                <TabsContent value="members" className="mt-0">
                  <MembersTable
                    tenantId={tenantId}
                    data={members.data}
                    isLoading={members.isLoading}
                    isError={members.isError}
                    canUpdateRole={canUpdateRole}
                    canRemove={canRemove}
                  />
                </TabsContent>
                <TabsContent value="invitations" className="mt-0">
                  <InvitationsTable
                    tenantId={tenantId}
                    data={invitations.data}
                    isLoading={invitations.isLoading}
                    canCancel={canInvite}
                  />
                </TabsContent>
              </CardContent>
            </Tabs>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

function StatCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  hint: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-muted text-muted-foreground">
          {icon}
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold leading-tight">{value}</p>
          <p className="text-xs text-muted-foreground">{hint}</p>
        </div>
      </CardContent>
    </Card>
  );
}
