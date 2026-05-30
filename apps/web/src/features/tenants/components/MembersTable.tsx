import { useMemo, useState } from "react";
import {
  type ColumnDef,
  type SortingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  getFacetedRowModel,
  getFacetedUniqueValues,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
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
  user: "Usuario",
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

export interface MembersTableProps {
  tenantId: string;
  data: Member[] | undefined;
  isLoading: boolean;
  isError: boolean;
  canUpdateRole: boolean;
  canRemove: boolean;
}

export function MembersTable({
  tenantId,
  data,
  isLoading,
  isError,
  canUpdateRole,
  canRemove,
}: MembersTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});

  const updateRoleMut = useUpdateMemberRoleMutation(tenantId);
  const removeMut = useRemoveMemberMutation(tenantId);

  const columns = useMemo<ColumnDef<Member>[]>(
    () => [
      {
        id: "user",
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
                      onSelect={() => removeMut.mutate({ userId: member.user_id })}
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
    [canRemove, canUpdateRole, removeMut, updateRoleMut],
  );

  const table = useReactTable({
    data: data ?? [],
    columns,
    state: { sorting, globalFilter, columnVisibility },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onColumnVisibilityChange: setColumnVisibility,
    getRowId: (row) => row.user_id,
    globalFilterFn: (row, _columnId, value) => {
      const needle = String(value).toLowerCase();
      if (!needle) return true;
      const member = row.original;
      return (
        member.user_id.toLowerCase().includes(needle) ||
        member.role.toLowerCase().includes(needle) ||
        (member.display_name?.toLowerCase().includes(needle) ?? false) ||
        (member.email?.toLowerCase().includes(needle) ?? false)
      );
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getFacetedRowModel: getFacetedRowModel(),
    getFacetedUniqueValues: getFacetedUniqueValues(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 10 } },
  });

  const roleColumn = table.getColumn("role");
  const statusColumn = table.getColumn("status");
  const isFiltered = globalFilter.length > 0 || table.getState().columnFilters.length > 0;

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
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
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
          <p className="text-xs text-muted-foreground">
            {table.getFilteredRowModel().rows.length} resultado(s)
          </p>
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
      <div className="overflow-hidden rounded-md border">
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
        totalCount={table.getFilteredRowModel().rows.length}
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
