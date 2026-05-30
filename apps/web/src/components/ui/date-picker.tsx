import * as React from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { CalendarIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export interface DatePickerProps {
  id?: string;
  value: string;
  onChange: (iso: string) => void;
  placeholder?: string;
  disabled?: boolean;
  "aria-invalid"?: boolean;
  className?: string;
}

function isoToDate(iso: string): Date | undefined {
  if (iso === "") return undefined;
  // `YYYY-MM-DD` parsed as local midnight to avoid the UTC shift that
  // would happen with `new Date("2026-05-27")` (treated as UTC by JS).
  const parts = iso.split("-");
  if (parts.length !== 3) return undefined;
  const [y, m, d] = parts.map(Number) as [number, number, number];
  if (Number.isNaN(y) || Number.isNaN(m) || Number.isNaN(d)) return undefined;
  return new Date(y, m - 1, d);
}

function dateToIso(date: Date): string {
  return format(date, "yyyy-MM-dd");
}

export function DatePicker({
  id,
  value,
  onChange,
  placeholder = "Selecciona una fecha",
  disabled = false,
  className,
  ...rest
}: DatePickerProps) {
  const [open, setOpen] = React.useState(false);
  const selected = isoToDate(value);
  const label = selected !== undefined ? format(selected, "PPP", { locale: es }) : placeholder;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          id={id}
          variant="outline"
          disabled={disabled}
          aria-invalid={rest["aria-invalid"]}
          className={cn(
            "w-full justify-start text-left font-normal",
            selected === undefined && "text-muted-foreground",
            className,
          )}
        >
          <CalendarIcon className="mr-2 size-4" />
          {label}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto overflow-hidden p-0" align="start">
        <Calendar
          mode="single"
          selected={selected}
          {...(selected !== undefined ? { defaultMonth: selected } : {})}
          locale={es}
          onSelect={(d) => {
            onChange(d ? dateToIso(d) : "");
            setOpen(false);
          }}
        />
      </PopoverContent>
    </Popover>
  );
}
