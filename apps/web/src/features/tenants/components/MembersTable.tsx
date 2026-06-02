import { useCallback, useEffect, useMemo, useState } from "react";
import {
  type ColumnDef,
  type ColumnFiltersState,
  type OnChangeFn,
  type PaginationState,
  type SortingState,
  type Updater,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  getFacetedRowModel,
  getFacetedUniqueValues,
  useReactTable,
} from "@tanstack/react-table";
import {
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  CircleCheck,
  CircleOff,
  MoreHorizontal,
  Search,
  Settings2,
  Shield,
  ShieldCheck,
  X,
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Member, UpdateMemberRoleInput } from "../api/endpoints";
import { useRemoveMemberMutation, useUpdateMemberRoleMutation } from "../api/hooks";
import { DataTableFacetedFilter } from "./DataTableFacetedFilter";
import { DestructiveActionDialog } from "@/components/dialog/destructive-action-dialog";

type RoleValue = UpdateMemberRoleInput["role"];

const ROLE_VARIANTS: Record<Member["role"], "default" | "secondary" | "outline" | "ok"> = {
  owner: "default",
  admin: "ok",
  accountant: "secondary",
  salesperson: "secondary",
  viewer: "outline",
};

const ROLE_LABELS: Record<Member["role"], string> = {
  owner: "Propietario",
  admin: "Administrador",
  accountant: "Contador",
  salesperson: "Vendedor",
  viewer: "Lector",
};

const ASSIGNABLE_ROLES: ReadonlyArray<RoleValue> = ["admin", "accountant", "salesperson", "viewer"];

const COLUMN_LABELS: Record<string, string> = {
  display_name: "Usuario",
  email: "Correo",
  role: "Rol",
  status: "Estado",
};

const ROLE_FILTER_OPTIONS = [
  { value: "owner", label: ROLE_LABELS.owner, icon: ShieldCheck },
  { value: "admin", label: ROLE_LABELS.admin, icon: Shield },
  { value: "accountant", label: ROLE_LABELS.accountant, icon: Shield },
  { value: "salesperson", label: ROLE_LABELS.salesperson, icon: Shield },
  { value: "viewer", label: ROLE_LABELS.viewer, icon: Shield },
] as const;

const STATUS_FILTER_OPTIONS = [
  { value: "active", label: "Activo", icon: CircleCheck },
  { value: "removed", label: "Removido", icon: CircleOff },
] as const;

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

function initialsFrom(displayName: string | null | undefined, fallback: string): string {
  const source = (displayName ?? "").trim();
  if (source.length > 0) {
    const parts = source.split(/\s+/);
    const first = parts[0]?.charAt(0) ?? "";
    const second = parts[1]?.charAt(0) ?? "";
    return (first + second || first).toUpperCase();
  }
  return fallback.slice(0, 2).toUpperCase();
}

// View-state slice that's worth syncing to URL search params. Column
// visibility lives outside this — it's a per-user preference, not a
// shareable view of the data.
export interface MembersTableViewState {
  sorting: SortingState;
  columnFilters: ColumnFiltersState;
  globalFilter: string;
  pagination: PaginationState;
}

export const DEFAULT_MEMBERS_TABLE_VIEW_STATE: MembersTableViewState = {
  sorting: [],
  columnFilters: [],
  globalFilter: "",
  pagination: { pageIndex: 0, pageSize: 10 },
};

export interface MembersTableProps {
  tenantId: string;
  data: Member[] | undefined;
  /** Filtered total reported by the API; used to compute pageCount in
   *  manual pagination mode and to render the result counter. */
  total?: number;
  isLoading: boolean;
  isError: boolean;
  canUpdateRole: boolean;
  canRemove: boolean;
  // Pass both to operate the table as a controlled component (the route
  // does this to round-trip state through URL search params). Pass
  // neither for the previous self-contained behavior (tests, isolated
  // usage).
  viewState?: MembersTableViewState;
  onViewStateChange?: (next: MembersTableViewState) => void;
}

function resolveUpdater<T>(updater: Updater<T>, prev: T): T {
  return typeof updater === "function" ? (updater as (p: T) => T)(prev) : updater;
}

export function MembersTable({
  tenantId,
  data,
  total,
  isLoading,
  isError,
  canUpdateRole,
  canRemove,
  viewState,
  onViewStateChange,
}: MembersTableProps) {
  const isControlled = viewState !== undefined && onViewStateChange !== undefined;
  const [internalState, setInternalState] = useState<MembersTableViewState>(
    viewState ?? DEFAULT_MEMBERS_TABLE_VIEW_STATE,
  );
  const currentState = isControlled ? viewState : internalState;
  const setState = useCallback(
    (next: MembersTableViewState) => {
      if (isControlled) {
        onViewStateChange(next);
      } else {
        setInternalState(next);
      }
    },
    [isControlled, onViewStateChange],
  );
  const { sorting, columnFilters, globalFilter, pagination } = currentState;

  // `searchInput` updates on every keystroke so the field stays responsive;
  // the debounced value is what we push into `globalFilter` (which drives
  // the filtered row model + URL search param).
  const [searchInput, setSearchInput] = useState(globalFilter);
  const debouncedSearch = useDebouncedValue(searchInput, 250);
  useEffect(() => {
    if (debouncedSearch !== globalFilter) {
      setState({ ...currentState, globalFilter: debouncedSearch });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);
  // External resets (e.g. clearing the URL search params) should flow
  // back into the visible input value.
  useEffect(() => {
    if (globalFilter !== searchInput && globalFilter !== debouncedSearch) {
      setSearchInput(globalFilter);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [globalFilter]);

  const setSorting: OnChangeFn<SortingState> = (updater) =>
    setState({ ...currentState, sorting: resolveUpdater(updater, sorting) });
  const setColumnFilters: OnChangeFn<ColumnFiltersState> = (updater) =>
    setState({ ...currentState, columnFilters: resolveUpdater(updater, columnFilters) });
  const setGlobalFilter: OnChangeFn<string> = (updater) => {
    const next = resolveUpdater(updater, globalFilter);
    setState({ ...currentState, globalFilter: next });
    setSearchInput(next);
  };
  const setPagination: OnChangeFn<PaginationState> = (updater) =>
    setState({ ...currentState, pagination: resolveUpdater(updater, pagination) });

  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});

  const updateRoleMut = useUpdateMemberRoleMutation(tenantId);
  const removeMut = useRemoveMemberMutation(tenantId);
  const [pendingRemove, setPendingRemove] = useState<Member | null>(null);

  const columns = useMemo<ColumnDef<Member>[]>(
    () => [
      {
        // Column id aligns with the API sort key so the URL search
        // param `sort=display_name` round-trips cleanly to the table's
        // sorting state.
        id: "display_name",
        accessorFn: (row) => row.display_name ?? row.user_id,
        header: ({ column }) => (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="-ml-3 h-8 px-2"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          >
            Usuario
            <ArrowUpDown className="ml-1.5 h-3.5 w-3.5 opacity-60" />
          </Button>
        ),
        cell: ({ row }) => {
          const member = row.original;
          const displayName = member.display_name?.trim();
          const initials = initialsFrom(member.display_name, member.user_id);
          return (
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
                {initials}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {displayName && displayName.length > 0 ? displayName : "—"}
                </p>
                <p className="truncate font-mono text-[11px] text-muted-foreground">
                  {member.user_id}
                </p>
              </div>
            </div>
          );
        },
      },
      {
        id: "email",
        accessorFn: (row) => row.email ?? "",
        header: ({ column }) => (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="-ml-3 h-8 px-2"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          >
            Correo
            <ArrowUpDown className="ml-1.5 h-3.5 w-3.5 opacity-60" />
          </Button>
        ),
        cell: ({ row }) => {
          const email = row.original.email?.trim();
          if (!email) {
            return <span className="text-sm text-muted-foreground">—</span>;
          }
          return <span className="text-sm">{email}</span>;
        },
      },
      {
        accessorKey: "role",
        filterFn: (row, columnId, value) => {
          if (!Array.isArray(value) || value.length === 0) return true;
          return (value as string[]).includes(String(row.getValue(columnId)));
        },
        header: ({ column }) => (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="-ml-3 h-8 px-2"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          >
            Rol
            <ArrowUpDown className="ml-1.5 h-3.5 w-3.5 opacity-60" />
          </Button>
        ),
        cell: ({ row }) => {
          const member = row.original;
          const isOwner = member.role === "owner";
          const Icon = isOwner ? ShieldCheck : Shield;
          return (
            <Badge variant={ROLE_VARIANTS[member.role]} className="gap-1">
              <Icon className="h-3 w-3" />
              {ROLE_LABELS[member.role] ?? member.role}
            </Badge>
          );
        },
      },
      {
        accessorKey: "status",
        filterFn: (row, columnId, value) => {
          if (!Array.isArray(value) || value.length === 0) return true;
          return (value as string[]).includes(String(row.getValue(columnId)));
        },
        header: "Estado",
        cell: ({ row }) => {
          const status = row.original.status;
          return (
            <Badge variant={status === "active" ? "ok" : "outline"}>
              {status === "active" ? "Activo" : "Removido"}
            </Badge>
          );
        },
      },
      {
        id: "actions",
        header: () => <span className="sr-only">Acciones</span>,
        enableHiding: false,
        cell: ({ row }) => {
          const member = row.original;
          const isOwner = member.role === "owner";
          if (isOwner) return null;
          if (!canUpdateRole && !canRemove) return null;
          return (
            <div className="flex justify-end">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    aria-label={`Acciones de ${member.user_id}`}
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-52">
                  {canUpdateRole ? (
                    <DropdownMenuSub>
                      <DropdownMenuSubTrigger>Cambiar rol</DropdownMenuSubTrigger>
                      <DropdownMenuSubContent>
                        <DropdownMenuLabel>Rol</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuRadioGroup
                          value={member.role}
                          onValueChange={(value) =>
                            updateRoleMut.mutate({
                              userId: member.user_id,
                              role: value as RoleValue,
                            })
                          }
                        >
                          {ASSIGNABLE_ROLES.map((opt) => (
                            <DropdownMenuRadioItem
                              key={opt}
                              value={opt}
                              disabled={updateRoleMut.isPending}
                            >
                              {ROLE_LABELS[opt]}
                            </DropdownMenuRadioItem>
                          ))}
                        </DropdownMenuRadioGroup>
                      </DropdownMenuSubContent>
                    </DropdownMenuSub>
                  ) : null}
                  {canUpdateRole && canRemove ? <DropdownMenuSeparator /> : null}
                  {canRemove ? (
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onSelect={() => setPendingRemove(member)}
                      disabled={removeMut.isPending}
                    >
                      Remover
                    </DropdownMenuItem>
                  ) : null}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          );
        },
      },
    ],
    [canRemove, canUpdateRole, removeMut.isPending, updateRoleMut],
  );

  const table = useReactTable({
    data: data ?? [],
    columns,
    state: { sorting, columnFilters, globalFilter, pagination, columnVisibility },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange: setGlobalFilter,
    onPaginationChange: setPagination,
    onColumnVisibilityChange: setColumnVisibility,
    getRowId: (row) => row.user_id,
    // Server-side mode: the route forwards filter/sort/pagination to
    // the API and returns the matching slice. The table only renders
    // what it's given and surfaces state changes to the route so the
    // next refetch covers the new view.
    manualPagination: true,
    manualFiltering: true,
    manualSorting: true,
    // `rowCount` lets `getPageCount()` work without `getFilteredRowModel`.
    // Falls back to in-page data length when `total` isn't supplied
    // (e.g. legacy uncontrolled callers + the unit test renderer).
    rowCount: total ?? data?.length ?? 0,
    getCoreRowModel: getCoreRowModel(),
    // Facets are computed off the currently-loaded slice. With
    // server-side filtering they're approximations — accurate enough
    // for a multi-select "Rol" / "Estado" picker; revisit if the
    // product needs precise counts.
    getFacetedRowModel: getFacetedRowModel(),
    getFacetedUniqueValues: getFacetedUniqueValues(),
  });

  const roleColumn = table.getColumn("role");
  const statusColumn = table.getColumn("status");
  const isFiltered = searchInput.length > 0 || globalFilter.length > 0 || columnFilters.length > 0;

  if (isLoading) {
    return <Skeleton className="h-32 w-full" />;
  }
  if (isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>No se pudieron cargar los miembros.</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Buscar miembro..."
              className="pl-8"
            />
          </div>
          {roleColumn ? (
            <DataTableFacetedFilter column={roleColumn} title="Rol" options={ROLE_FILTER_OPTIONS} />
          ) : null}
          {statusColumn ? (
            <DataTableFacetedFilter
              column={statusColumn}
              title="Estado"
              options={STATUS_FILTER_OPTIONS}
            />
          ) : null}
          {isFiltered ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 px-2"
              onClick={() => {
                setSearchInput("");
                setGlobalFilter("");
                table.resetColumnFilters();
              }}
            >
              Limpiar
              <X className="ml-1.5 h-3.5 w-3.5" />
            </Button>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <p className="text-xs text-muted-foreground">{table.getRowCount()} resultado(s)</p>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button type="button" variant="outline" size="sm" className="h-8">
                <Settings2 className="mr-1.5 h-3.5 w-3.5" />
                Vista
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44">
              <DropdownMenuLabel>Columnas</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {table
                .getAllColumns()
                .filter((c) => c.getCanHide())
                .map((column) => (
                  <DropdownMenuCheckboxItem
                    key={column.id}
                    className="capitalize"
                    checked={column.getIsVisible()}
                    onCheckedChange={(value) => column.toggleVisibility(value === true)}
                  >
                    {COLUMN_LABELS[column.id] ?? column.id}
                  </DropdownMenuCheckboxItem>
                ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      {/* Desktop layout: the data table. Hidden below the md
          breakpoint so phones don't have to horizontally scroll
          a 5-column table. */}
      <div className="hidden md:block overflow-hidden rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="bg-muted/40 hover:bg-muted/40">
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length > 0 ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-sm text-muted-foreground"
                >
                  Sin miembros para mostrar.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {/* Mobile layout: one card per member ordered nombre,
          correo, rol badge, estado badge. Pagination is shared
          with the desktop layout via the same `<TablePagination>`
          below, so swiping through pages on mobile updates the
          desktop view when the operator rotates the device. */}
      <div className="md:hidden space-y-2">
        {table.getRowModel().rows.length > 0 ? (
          table.getRowModel().rows.map((row) => {
            const member = row.original;
            const initials = initialsFrom(member.display_name, member.user_id);
            const displayName = member.display_name?.trim();
            return (
              <div key={row.id} className="rounded-md border bg-card p-4 shadow-xs" role="listitem">
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
                    {initials}
                  </div>
                  <div className="min-w-0 flex-1 space-y-1">
                    <p className="truncate text-sm font-medium">
                      {displayName && displayName.length > 0 ? displayName : "—"}
                    </p>
                    {member.email ? (
                      <p className="truncate text-xs text-muted-foreground">{member.email}</p>
                    ) : null}
                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                      <Badge variant={ROLE_VARIANTS[member.role]}>{ROLE_LABELS[member.role]}</Badge>
                      <Badge variant={member.status === "active" ? "ok" : "outline"}>
                        {member.status === "active" ? "Activo" : "Removido"}
                      </Badge>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          <div className="rounded-md border bg-card p-6 text-center text-sm text-muted-foreground">
            Sin miembros para mostrar.
          </div>
        )}
      </div>
      <TablePagination
        pageIndex={table.getState().pagination.pageIndex}
        pageSize={table.getState().pagination.pageSize}
        pageCount={table.getPageCount()}
        canPrev={table.getCanPreviousPage()}
        canNext={table.getCanNextPage()}
        onPrev={() => table.previousPage()}
        onNext={() => table.nextPage()}
        onFirst={() => table.setPageIndex(0)}
        onLast={() => table.setPageIndex(table.getPageCount() - 1)}
        onPageSizeChange={(size) => table.setPageSize(size)}
        totalCount={table.getRowCount()}
      />
      <DestructiveActionDialog
        open={pendingRemove !== null}
        onOpenChange={(open) => {
          if (!open) setPendingRemove(null);
        }}
        title="Remover miembro"
        description={
          pendingRemove
            ? `¿Remover a ${pendingRemove.display_name ?? pendingRemove.email ?? "este miembro"} de la empresa? Perderá acceso inmediatamente.`
            : ""
        }
        confirmLabel="Sí, remover"
        cancelLabel="Volver"
        pending={removeMut.isPending}
        onConfirm={() => {
          if (pendingRemove === null) return;
          removeMut.mutate(
            { userId: pendingRemove.user_id },
            { onSettled: () => setPendingRemove(null) },
          );
        }}
      />
    </div>
  );
}

function TablePagination({
  pageIndex,
  pageSize,
  pageCount,
  canPrev,
  canNext,
  onPrev,
  onNext,
  onFirst,
  onLast,
  onPageSizeChange,
  totalCount,
}: {
  pageIndex: number;
  pageSize: number;
  pageCount: number;
  canPrev: boolean;
  canNext: boolean;
  onPrev: () => void;
  onNext: () => void;
  onFirst: () => void;
  onLast: () => void;
  onPageSizeChange: (size: number) => void;
  totalCount: number;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <p className="text-xs text-muted-foreground">{totalCount} fila(s) en total.</p>
      <div className="flex flex-wrap items-center justify-end gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Filas por página</span>
          <Select value={String(pageSize)} onValueChange={(v) => onPageSizeChange(Number(v))}>
            <SelectTrigger className="h-8 w-[72px]" aria-label="Filas por página">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAGE_SIZE_OPTIONS.map((opt) => (
                <SelectItem key={opt} value={String(opt)}>
                  {opt}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <span className="text-xs text-muted-foreground">
          Página {Math.min(pageIndex + 1, Math.max(pageCount, 1))} de {Math.max(pageCount, 1)}
        </span>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={onFirst}
            disabled={!canPrev}
            aria-label="Primera página"
          >
            <ChevronsLeft className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={onPrev}
            disabled={!canPrev}
            aria-label="Página anterior"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={onNext}
            disabled={!canNext}
            aria-label="Página siguiente"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={onLast}
            disabled={!canNext}
            aria-label="Última página"
          >
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
