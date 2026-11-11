/** What the course structure panel offers, including the way to clear the last unit. */

export type StartOverChoice = "draft" | "delete-components";

export function structureControls(unitCount: number): { startOver: boolean; deleteUnit: boolean } {
  return {
    startOver: true,
    deleteUnit: unitCount > 1,
  };
}

/** Delete-components clears every unit, including the last one. Reset draft leaves them. */
export function unitsAfterStartOver<T>(units: T[], choice: StartOverChoice): T[] {
  if (choice === "delete-components") return [];
  return units;
}
