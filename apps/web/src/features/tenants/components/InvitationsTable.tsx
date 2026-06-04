import { useMemo, useState } from "react";
import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown, Mail, Search } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Invitation } from "../api/endpoints";
import { useCancelInvitationMutation, useResendInvitationMutation } from "../api/hooks";
import { DestructiveActionDialog } from "@/components/dialog/destructive-action-dialog";

import { ROLE_LABELS } from "../lib/role-labels";

export interface InvitationsTableProps {
  tenantId: string;
  data: Invitation[] | undefined;
  isLoading: boolean;
  canCancel: boolean;
}

export function InvitationsTable({ tenantId, data, isLoading, canCancel }: InvitationsTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");
  const cancelMut = useCancelInvitationMutation(tenantId);
  const resendMut = useResendInvitationMutation(tenantId);
  const [pendingCancel, setPendingCancel] = useState<Invitation | null>(null);

  const pending = useMemo(() => (data ?? []).filter((i) => i.status === "pending"), [data]);

  const columns = useMemo<ColumnDef<Invitation>[]>(
    () => [
      {
        accessorKey: "email",
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
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm">{row.original.email}</span>
          </div>
        ),
      },
      {
        accessorKey: "proposed_role",
        header: "Rol propuesto",
        cell: ({ row }) => (
          <Badge variant="secondary">
            {ROLE_LABELS[row.original.proposed_role] ?? row.original.proposed_role}
          </Badge>
        ),
      },
      {
        accessorKey: "status",
        header: "Estado",
        cell: () => <Badge variant="warn">Pendiente</Badge>,
      },
      {
        id: "actions",
        header: () => <span className="sr-only">Acciones</span>,
        cell: ({ row }) => {
          if (!canCancel) return null;
          return (
            <div className="flex justify-end gap-1">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => resendMut.mutate({ invitationId: row.original.id })}
                disabled={resendMut.isPending || cancelMut.isPending}
              >
                {resendMut.isPending ? "Enviando…" : "Reenviar"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setPendingCancel(row.original)}
                disabled={cancelMut.isPending || resendMut.isPending}
              >
                Cancelar
              </Button>
            </div>
          );
        },
      },
    ],
    [canCancel, cancelMut, resendMut],
  );

  const table = useReactTable({
    data: pending,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    globalFilterFn: (row, _columnId, value) => {
      const needle = String(value).toLowerCase();
      if (!needle) return true;
      const inv = row.original;
      const roleLabel = (ROLE_LABELS[inv.proposed_role] ?? inv.proposed_role).toLowerCase();
      return inv.email.toLowerCase().includes(needle) || roleLabel.includes(needle);
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 10 } },
  });

  if (isLoading) {
    return <Skeleton className="h-32 w-full" />;
  }

  if (pending.length === 0) {
    return (
      <Alert>
        <AlertDescription>No hay invitaciones pendientes.</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-3">
      {cancelMut.isError ? (
        <Alert variant="destructive" role="alert">
          <AlertDescription>No se pudo cancelar la invitación.</AlertDescription>
        </Alert>
      ) : null}
      {resendMut.isError ? (
        <Alert variant="destructive" role="alert">
          <AlertDescription>No se pudo reenviar la invitación.</AlertDescription>
        </Alert>
      ) : null}
      {resendMut.isSuccess ? (
        <Alert role="status">
          <AlertDescription>Invitación reenviada con un nuevo enlace.</AlertDescription>
        </Alert>
      ) : null}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={globalFilter}
            onChange={(e) => setGlobalFilter(e.target.value)}
            placeholder="Buscar invitación..."
            className="pl-8"
          />
        </div>
        <p className="text-xs text-muted-foreground">
          {table.getFilteredRowModel().rows.length} pendiente(s)
        </p>
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
            {table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <DestructiveActionDialog
        open={pendingCancel !== null}
        onOpenChange={(open) => {
          if (!open) setPendingCancel(null);
        }}
        title="Cancelar invitación"
        description={
          pendingCancel
            ? `¿Cancelar la invitación enviada a ${pendingCancel.email}? Esta acción no se puede deshacer.`
            : ""
        }
        confirmLabel="Sí, cancelar"
        cancelLabel="Volver"
        pending={cancelMut.isPending}
        onConfirm={() => {
          if (pendingCancel === null) return;
          cancelMut.mutate(
            { invitationId: pendingCancel.id },
            { onSettled: () => setPendingCancel(null) },
          );
        }}
      />
    </div>
  );
}
