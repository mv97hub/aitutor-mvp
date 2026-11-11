import type { KcBlueprint, KcBlueprintComponent } from "./kc.ts";

type Spot = { unit: number; index: number };

function copy(blueprint: KcBlueprint): KcBlueprint {
  return {
    outcomes: [...blueprint.outcomes],
    units: blueprint.units.map((unit) => ({
      ...unit,
      components: unit.components.map((item) => ({ ...item, prerequisites: [...item.prerequisites] })),
    })),
  };
}

function flat(blueprint: KcBlueprint): { spot: Spot; item: KcBlueprintComponent }[] {
  return blueprint.units.flatMap((unit, unitIndex) =>
    unit.components.map((item, index) => ({ spot: { unit: unitIndex, index }, item })),
  );
}

export function componentCount(blueprint: KcBlueprint): number {
  return blueprint.units.reduce((total, unit) => total + unit.components.length, 0);
}

export function editComponent(
  blueprint: KcBlueprint,
  spot: Spot,
  change: Partial<Pick<KcBlueprintComponent, "title" | "summary" | "prerequisites">>,
): KcBlueprint {
  const next = copy(blueprint);
  const item = next.units[spot.unit]?.components[spot.index];
  if (item) Object.assign(item, change);
  return next;
}

export function editUnit(blueprint: KcBlueprint, unit: number, change: { title?: string; summary?: string }): KcBlueprint {
  const next = copy(blueprint);
  const row = next.units[unit];
  if (row) Object.assign(row, change);
  return next;
}

export function editOutcomes(blueprint: KcBlueprint, text: string): KcBlueprint {
  return {
    ...copy(blueprint),
    outcomes: text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
  };
}

/** Move a component one place in the whole course order. It can cross into the next unit. */
export function moveComponent(blueprint: KcBlueprint, spot: Spot, direction: -1 | 1): KcBlueprint {
  const rows = flat(blueprint);
  const at = rows.findIndex((row) => row.spot.unit === spot.unit && row.spot.index === spot.index);
  const to = at + direction;
  if (at < 0 || to < 0 || to >= rows.length) return blueprint;
  const next = copy(blueprint);
  const from = next.units[spot.unit]!.components;
  const [item] = from.splice(spot.index, 1);
  const target = rows[to]!.spot;
  const into = next.units[target.unit]!.components;
  if (target.unit === spot.unit) into.splice(target.index, 0, item!);
  else if (direction > 0) into.splice(0, 0, item!);
  else into.splice(Math.max(into.length - 1, 0), 0, item!);
  return pruneLinks(next);
}

/** A prerequisite has to come earlier in the course. Drop any link a move turned into a forward link. */
export function pruneLinks(blueprint: KcBlueprint): KcBlueprint {
  const seen = new Set<string>();
  for (const unit of blueprint.units) {
    for (const item of unit.components) {
      item.prerequisites = item.prerequisites.filter((code) => seen.has(code));
      if (item.code) seen.add(item.code);
    }
  }
  return blueprint;
}

/** Drop a component and any prerequisite link that pointed at it. */
export function removeComponent(blueprint: KcBlueprint, spot: Spot): KcBlueprint {
  const next = copy(blueprint);
  const [gone] = next.units[spot.unit]?.components.splice(spot.index, 1) ?? [];
  if (!gone) return blueprint;
  for (const unit of next.units) {
    for (const item of unit.components) {
      item.prerequisites = item.prerequisites.filter((code) => code !== gone.code);
    }
  }
  return next;
}

/** A new row has no code. The API assigns one when the blueprint is saved. */
export function addComponent(blueprint: KcBlueprint, unit: number, title = "New component"): KcBlueprint {
  const next = copy(blueprint);
  next.units[unit]?.components.push({ code: "", title, summary: "", prerequisites: [] });
  return next;
}

/** Codes that may be a prerequisite of this spot: every component that comes before it. */
export function earlierCodes(blueprint: KcBlueprint, spot: Spot): string[] {
  const rows = flat(blueprint);
  const at = rows.findIndex((row) => row.spot.unit === spot.unit && row.spot.index === spot.index);
  return rows
    .slice(0, Math.max(at, 0))
    .map((row) => row.item.code)
    .filter(Boolean);
}

export function parseCodes(text: string): string[] {
  return text
    .split(/[,\s]+/)
    .map((code) => code.trim())
    .filter(Boolean);
}
