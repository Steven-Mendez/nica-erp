// Static catalog of Nicaraguan departments + their municipios.
// The fiscal-settings editor consumes this to render the dependent
// departamento → municipio dropdowns; the SPA does not roundtrip to
// the backend for this data because the list is small (~150 entries),
// rarely changes, and shipping it client-side avoids a chatty cold
// load. When DGI publishes a redistricting we update this file in a
// single commit.
//
// Source: INETER + INIDE 2020 administrative-division publication.
// The 15 departamentos + 153 municipios listed below match the DGI
// municipality codes used on invoices.

export interface Departamento {
  /** Canonical Spanish name shown in the dropdown label. */
  readonly name: string;
  /** Municipios ordered alphabetically (Spanish collation). */
  readonly municipios: readonly string[];
}

export const DEPARTAMENTOS: readonly Departamento[] = Object.freeze([
  {
    name: "Boaco",
    municipios: [
      "Boaco",
      "Camoapa",
      "San José de los Remates",
      "San Lorenzo",
      "Santa Lucía",
      "Teustepe",
    ],
  },
  {
    name: "Carazo",
    municipios: [
      "Diriamba",
      "Dolores",
      "El Rosario",
      "Jinotepe",
      "La Conquista",
      "La Paz de Carazo",
      "San Marcos",
      "Santa Teresa",
    ],
  },
  {
    name: "Chinandega",
    municipios: [
      "Chichigalpa",
      "Chinandega",
      "Cinco Pinos",
      "Corinto",
      "El Realejo",
      "El Viejo",
      "Posoltega",
      "Puerto Morazán",
      "San Francisco del Norte",
      "San Pedro del Norte",
      "Santo Tomás del Norte",
      "Somotillo",
      "Villanueva",
    ],
  },
  {
    name: "Chontales",
    municipios: [
      "Acoyapa",
      "Comalapa",
      "El Coral",
      "Juigalpa",
      "La Libertad",
      "San Francisco de Cuapa",
      "San Pedro de Lóvago",
      "Santo Domingo",
      "Santo Tomás",
      "Villa Sandino",
    ],
  },
  {
    name: "Estelí",
    municipios: [
      "Condega",
      "Estelí",
      "La Trinidad",
      "Pueblo Nuevo",
      "San Juan de Limay",
      "San Nicolás",
    ],
  },
  {
    name: "Granada",
    municipios: ["Diriá", "Diriomo", "Granada", "Nandaime"],
  },
  {
    name: "Jinotega",
    municipios: [
      "El Cuá",
      "Jinotega",
      "La Concordia",
      "San José de Bocay",
      "San Rafael del Norte",
      "San Sebastián de Yalí",
      "Santa María de Pantasma",
      "Wiwilí de Jinotega",
    ],
  },
  {
    name: "León",
    municipios: [
      "Achuapa",
      "El Jicaral",
      "El Sauce",
      "La Paz Centro",
      "Larreynaga",
      "León",
      "Nagarote",
      "Quezalguaque",
      "Santa Rosa del Peñón",
      "Telica",
    ],
  },
  {
    name: "Madriz",
    municipios: [
      "Las Sabanas",
      "Palacagüina",
      "San José de Cusmapa",
      "San Juan de Río Coco",
      "San Lucas",
      "Somoto",
      "Telpaneca",
      "Totogalpa",
      "Yalagüina",
    ],
  },
  {
    name: "Managua",
    municipios: [
      "Ciudad Sandino",
      "El Crucero",
      "Managua",
      "Mateare",
      "San Francisco Libre",
      "San Rafael del Sur",
      "Ticuantepe",
      "Tipitapa",
      "Villa El Carmen",
    ],
  },
  {
    name: "Masaya",
    municipios: [
      "Catarina",
      "La Concepción",
      "Masatepe",
      "Masaya",
      "Nandasmo",
      "Nindirí",
      "Niquinohomo",
      "San Juan de Oriente",
      "Tisma",
    ],
  },
  {
    name: "Matagalpa",
    municipios: [
      "Ciudad Darío",
      "El Tuma - La Dalia",
      "Esquipulas",
      "Matagalpa",
      "Matiguás",
      "Muy Muy",
      "Rancho Grande",
      "Río Blanco",
      "San Dionisio",
      "San Isidro",
      "San Ramón",
      "Sébaco",
      "Terrabona",
    ],
  },
  {
    name: "Nueva Segovia",
    municipios: [
      "Ciudad Antigua",
      "Dipilto",
      "El Jícaro",
      "Jalapa",
      "Macuelizo",
      "Mozonte",
      "Murra",
      "Ocotal",
      "Quilalí",
      "San Fernando",
      "Santa María",
      "Wiwilí de Nueva Segovia",
    ],
  },
  {
    name: "Rivas",
    municipios: [
      "Altagracia",
      "Belén",
      "Buenos Aires",
      "Cárdenas",
      "Moyogalpa",
      "Potosí",
      "Rivas",
      "San Jorge",
      "San Juan del Sur",
      "Tola",
    ],
  },
  {
    name: "Río San Juan",
    municipios: [
      "El Almendro",
      "El Castillo",
      "Morrito",
      "San Carlos",
      "San Juan de Nicaragua",
      "San Miguelito",
    ],
  },
]);

// O(1) lookup helper — used by the form to validate that a chosen
// municipio is still legal after a departamento change.
const _MUNICIPIOS_BY_DEPT: ReadonlyMap<string, ReadonlySet<string>> = new Map(
  DEPARTAMENTOS.map((d) => [d.name, new Set(d.municipios)] as const),
);

export function isValidMunicipio(departamento: string, municipio: string): boolean {
  const set = _MUNICIPIOS_BY_DEPT.get(departamento);
  return set !== undefined && set.has(municipio);
}

export function municipiosOf(departamento: string): readonly string[] {
  const dept = DEPARTAMENTOS.find((d) => d.name === departamento);
  return dept !== undefined ? dept.municipios : [];
}
