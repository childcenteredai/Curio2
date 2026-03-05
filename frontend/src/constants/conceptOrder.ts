/**
 * Fixed concept order from kg.json (Hair Stands Up Near a Balloon).
 * CONCEPT_GRID_POSITIONS: [row, col] 1-based grid position for each concept.
 * CONCEPT_CONNECTIONS: pairs of concept indices that connect (each pair once).
 */
export const CONCEPT_ORDER = [
  'Invisible Force',
  'Energy from Rubbing',
  'Charges',
  'Electrons',
  'Different Charges',
  'Push and Pull',
  'Material Properties',
  'Test the Effect of Static Electricity',
] as const

/** Grid position for each concept (by CONCEPT_ORDER index): [row, col] */
export const CONCEPT_GRID_POSITIONS: [number, number][] = [
  [1, 1], /* 0: Force at a Distance - top-left */
  [2, 1], /* 1: Energy from Rubbing */
  [3, 2], /* 2: Charges */
  [3, 3], /* 3: Electrons - only connects to Charges */
  [2, 2], /* 4: Imbalance of Charges (Different Charges Between Objects) */
  [1, 3], /* 5: Attraction & Repulsion (Push and Pull) */
  [2, 5], /* 6: Material Properties - only connects to Testing */
  [1, 5], /* 7: Testing the Effect of Static Electricity - top-right */
]

/** Pairs of concept indices to connect with lines. Electrons-Charges, Material-Testing are special. */
export const CONCEPT_CONNECTIONS: [number, number][] = [
  [0, 1], /* Force - Energy */
  [0, 5], /* Force - Push and Pull */
  [1, 4], /* Energy - Imbalance */
  [5, 7], /* Push and Pull - Testing */
  [4, 2], /* Imbalance - Charges */
  [2, 3], /* Charges - Electrons */
  [6, 7], /* Material - Testing */
]

export type ConceptKey = (typeof CONCEPT_ORDER)[number]
