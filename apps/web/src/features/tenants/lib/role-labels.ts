// apps/web/src/features/tenants/lib/role-labels.ts
//
// Shared Spanish labels for every tenant role the backend emits. The
// SPA used to maintain three independent maps (members table,
// invitations table, sidebar workspace switcher) and the empresa-list
// cards rendered the raw English code (audit F-033). One module here
// is the single source of truth; route components import this helper.

export type TenantRole = "owner" | "admin" | "accountant" | "salesperson" | "viewer";

export const ROLE_LABELS: Record<TenantRole, string> = {
  owner: "Propietario",
  admin: "Administrador",
  accountant: "Contador",
  salesperson: "Vendedor",
  viewer: "Visualizador",
};

export const roleLabel = (role: string): string => {
  return ROLE_LABELS[role as TenantRole] ?? role;
};
