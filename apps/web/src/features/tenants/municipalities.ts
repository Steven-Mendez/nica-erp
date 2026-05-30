// Canonical catalog of Nicaraguan municipalities accepted by the
// `Municipality` value object on the backend
// (apps/api/src/contexts/tenants/domain/municipality.py). The two
// arrays MUST stay in sync — when one grows, the other grows in the
// same PR.

export const MUNICIPALITIES = [
  "Managua",
  "León",
  "Granada",
  "Masaya",
  "Estelí",
  "Matagalpa",
  "Chinandega",
  "Jinotega",
  "Nueva Segovia",
  "Madriz",
  "Boaco",
  "Carazo",
  "Chontales",
  "Rivas",
  "Río San Juan",
  "RAAN",
  "RAAS",
] as const;

export type Municipality = (typeof MUNICIPALITIES)[number];
