export type KcUnitStatus = "completed" | "in_progress" | "not_started";

export type KcProgressBlock = {
  id: string;
  type: string;
  type_label: string;
  status: "completed" | "active";
  outcome?: "passed" | "revealed";
  attempts?: number;
  rubric?: string;
};

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
  blocks?: KcProgressBlock[];
  rubric?: string[];
  result?: {
    status: "known" | "fragile";
    rubric_met: string[];
    justification: string;
    strong: string;
    work_on: string;
  } | null;
};

/** Finished means known or fragile. The known count stays separate. */
export function courseScore(units: KcProgressUnit[], known: number) {
  const targets = units.filter((unit) => !unit.patch);
  const total = targets.length;
  const finished = targets.filter((unit) => unit.status === "completed").length;
  const percent = total <= 0 ? 0 : Math.floor((finished * 100 + Math.floor(total / 2)) / total);
  return { percent, finished, total, known };
}

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
