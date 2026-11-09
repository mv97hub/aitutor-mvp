export type KcUnitStatus = "completed" | "in_progress" | "not_started";

export type KcProgressUnit = {
  id: string;
  code: string;
  title: string;
  kc_type: string | null;
  summary?: string;
  patch: boolean;
  status: KcUnitStatus;
  mastery?: "" | "known" | "fragile";
  finished_blocks?: number;
  total_blocks?: number;
  rubric?: string[];
  result?: {
    status: "known" | "fragile";
    rubric_met: string[];
    justification: string;
    strong: string;
    work_on: string;
  } | null;
};

export function unitLine(unit: KcProgressUnit): string {
  const patch = unit.patch ? " patch" : "";
  if (unit.status === "completed" && (unit.mastery === "known" || unit.mastery === "fragile")) {
    return `${unit.mastery}${patch}`;
  }
  if (unit.status === "in_progress") {
    return `${unit.finished_blocks ?? 0} of ${unit.total_blocks ?? 0} blocks${patch}`;
  }
  const name = unit.summary || "No blocks yet";
  return unit.patch ? `${name} patch` : name;
}

export function unitsByStatus(units: KcProgressUnit[]) {
  return {
    completed: units.filter((unit) => unit.status === "completed"),
    in_progress: units.filter((unit) => unit.status === "in_progress"),
    not_started: units.filter((unit) => unit.status === "not_started"),
  };
}

/** Join course units onto network nodes by component code. */
export function statusByCode(units: KcProgressUnit[]): Record<string, KcUnitStatus> {
  return Object.fromEntries(units.map((unit) => [unit.code, unit.status]));
}

export function masteryByCode(units: KcProgressUnit[]): Record<string, string> {
  return Object.fromEntries(
    units
      .filter((unit) => unit.status === "completed" && (unit.mastery === "known" || unit.mastery === "fragile"))
      .map((unit) => [unit.code, unit.mastery as string]),
  );
}

export function networkStatusClass(status: KcUnitStatus | undefined): string {
  if (status === "completed") return "is-completed";
  if (status === "in_progress") return "is-in-progress";
  if (status === "not_started") return "is-not-started";
  return "";
}
