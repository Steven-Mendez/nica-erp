// apps/web/src/features/tenants/lib/departamentos.ts
//
// Canonical list of the 15 Nicaraguan departamentos + 2 autonomous
// regions (RAAN, RAAS). Used by both the empresa-creation wizard and
// the fiscal-settings editor so the two screens cannot drift again
// (audit F-006).

export const DEPARTAMENTOS = [
  "Boaco",
  "Carazo",
  "Chinandega",
  "Chontales",
  "Estelí",
  "Granada",
  "Jinotega",
  "León",
  "Madriz",
  "Managua",
  "Masaya",
  "Matagalpa",
  "Nueva Segovia",
  "RAAN",
  "RAAS",
  "Rivas",
  "Río San Juan",
] as const;

export type Departamento = (typeof DEPARTAMENTOS)[number];

export const isDepartamento = (value: string): value is Departamento => {
  return (DEPARTAMENTOS as readonly string[]).includes(value);
};
