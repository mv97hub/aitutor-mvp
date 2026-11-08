export type KcUnitStatus = "completed" | "in_progress" | "not_started";

export type KcProgressUnit = {
  id: string;
  code: string;
  title: string;
  kc_type: string | null;
  summary?: string;
  patch: boolean;
  status: KcUnitStatus;
};

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

export function networkStatusClass(status: KcUnitStatus | undefined): string {
  if (status === "completed") return "is-completed";
  if (status === "in_progress") return "is-in-progress";
  if (status === "not_started") return "is-not-started";
  return "";
}
