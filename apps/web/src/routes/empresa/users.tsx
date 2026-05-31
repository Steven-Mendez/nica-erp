import { useCallback, useMemo } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { MailQuestion, Users } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useHasPermission } from "@/api/useHasPermission";
import { useMeQuery } from "@/features/auth/api/hooks";
import { InvitationsTable } from "@/features/tenants/components/InvitationsTable";
import { InviteMemberDialog } from "@/features/tenants/components/InviteMemberDialog";
import {
  DEFAULT_MEMBERS_TABLE_VIEW_STATE,
  MembersTable,
  type MembersTableViewState,
} from "@/features/tenants/components/MembersTable";
import type { ListMembersParams } from "@/features/tenants/api/endpoints";
import { useInvitationsQuery, useMembersQuery } from "@/features/tenants/api/hooks";
import { useDocumentTitle } from "@/lib/useDocumentTitle";
import type { EmpresaUsersSearch } from "@/router";

const DEFAULT_PAGE_SIZE = DEFAULT_MEMBERS_TABLE_VIEW_STATE.pagination.pageSize;

// Project URL search params into the request shape `useMembersQuery`
// expects. Missing fields collapse to "no filter" / default page.
function searchToParams(search: EmpresaUsersSearch): ListMembersParams {
  const params: ListMembersParams = {
    limit: search.size ?? DEFAULT_PAGE_SIZE,
    offset: ((search.page ?? 1) - 1) * (search.size ?? DEFAULT_PAGE_SIZE),
  };
  if (search.q && search.q.length > 0) params.q = search.q;
  if (search.roles && search.roles.length > 0) params.roles = search.roles;
  if (search.statuses && search.statuses.length > 0) params.statuses = search.statuses;
  if (search.sort) params.sort = search.sort;
  if (search.dir) params.dir = search.dir;
  return params;
}

// Round-trip the URL search params into the controlled state TanStack
// Table expects. Empty / missing params collapse to the table's defaults
// so a bare `/empresa/users` URL stays clean.
function searchToViewState(search: EmpresaUsersSearch): MembersTableViewState {
  const columnFilters: MembersTableViewState["columnFilters"] = [];
  if (search.roles && search.roles.length > 0) {
    columnFilters.push({ id: "role", value: search.roles });
  }
  if (search.statuses && search.statuses.length > 0) {
    columnFilters.push({ id: "status", value: search.statuses });
  }
  return {
    sorting: search.sort ? [{ id: search.sort, desc: search.dir === "desc" }] : [],
    columnFilters,
    globalFilter: search.q ?? "",
    pagination: {
      pageIndex: (search.page ?? 1) - 1,
      pageSize: search.size ?? DEFAULT_PAGE_SIZE,
    },
  };
}

function viewStateToSearch(
  view: MembersTableViewState,
  prev: EmpresaUsersSearch,
): EmpresaUsersSearch {
  const next: EmpresaUsersSearch = { ...prev };
  // q
  if (view.globalFilter.length > 0) next.q = view.globalFilter;
  else delete next.q;
  // sort
  const firstSort = view.sorting[0];
  if (firstSort) {
    next.sort = firstSort.id as EmpresaUsersSearch["sort"];
    next.dir = firstSort.desc ? "desc" : "asc";
  } else {
    delete next.sort;
    delete next.dir;
  }
  // roles / statuses
  const rolesFilter = view.columnFilters.find((f) => f.id === "role");
  if (rolesFilter && Array.isArray(rolesFilter.value) && rolesFilter.value.length > 0) {
    next.roles = rolesFilter.value as EmpresaUsersSearch["roles"];
  } else {
    delete next.roles;
  }
  const statusFilter = view.columnFilters.find((f) => f.id === "status");
  if (statusFilter && Array.isArray(statusFilter.value) && statusFilter.value.length > 0) {
    next.statuses = statusFilter.value as EmpresaUsersSearch["statuses"];
  } else {
    delete next.statuses;
  }
  // page / size — only store when they diverge from defaults
  if (view.pagination.pageIndex > 0) next.page = view.pagination.pageIndex + 1;
  else delete next.page;
  if (view.pagination.pageSize !== DEFAULT_PAGE_SIZE) next.size = view.pagination.pageSize;
  else delete next.size;
  return next;
}

export function EmpresaUsuariosRoute() {
  useDocumentTitle("Usuarios");
  const me = useMeQuery();
  const tenantId = me.data?.active_tenant ?? "";
  const search = useSearch({ from: "/empresa/users" });
  const navigate = useNavigate({ from: "/empresa/users" });
  const memberParams = useMemo(() => searchToParams(search), [search]);
  const members = useMembersQuery(tenantId, memberParams);
  const invitations = useInvitationsQuery(tenantId);
  const canInvite = useHasPermission("members:invite");
  const canRemove = useHasPermission("members:remove");
  const canUpdateRole = useHasPermission("members:update-role");

  const viewState = useMemo(() => searchToViewState(search), [search]);
  const handleViewStateChange = useCallback(
    (next: MembersTableViewState) => {
      void navigate({
        search: (prev) => viewStateToSearch(next, prev as EmpresaUsersSearch),
        replace: true,
      });
    },
    [navigate],
  );

  const tab = search.tab ?? "members";
  const handleTabChange = useCallback(
    (value: string) => {
      void navigate({
        search: (prev) => {
          const nextTab = value === "invitations" ? "invitations" : "members";
          const base = { ...(prev as EmpresaUsersSearch) };
          if (nextTab === "members") {
            delete base.tab;
            return base;
          }
          return { ...base, tab: nextTab };
        },
        replace: true,
      });
    },
    [navigate],
  );

  // `total` is the FILTERED count (matches the current `q`/role/status
  // predicates); fine for the tab badge so long as the user can see
  // it changes with their filters. There is no separate unfiltered
  // count endpoint at this point.
  const memberCount = members.data?.total ?? 0;
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
            <Tabs value={tab} onValueChange={handleTabChange} className="w-full">
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
                    data={members.data?.items}
                    total={members.data?.total ?? 0}
                    isLoading={members.isLoading}
                    isError={members.isError}
                    canUpdateRole={canUpdateRole}
                    canRemove={canRemove}
                    viewState={viewState}
                    onViewStateChange={handleViewStateChange}
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
