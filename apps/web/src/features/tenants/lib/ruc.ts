// apps/web/src/features/tenants/lib/ruc.ts
//
// RUC canonical-form helper. Audit F-006 noted the wizard and the
// settings editor showed different placeholders; the canonical form
// is 13 digits + 1 trailing letter, stored without dashes.

export const RUC_PLACEHOLDER = "J03-100000-00010";

export const normalizeRuc = (raw: string): string => {
  return raw.toUpperCase().replace(/[^A-Z0-9]/g, "");
};
