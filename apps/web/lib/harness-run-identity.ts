/** Fields on a stored run that identify it for POST /api/kc/harness/agent/runs. */

export type HarnessRunPlan = {
  course_ids?: unknown;
  persona_ids?: unknown;
  tutor_models?: unknown;
  tutor_model?: unknown;
  child_model?: unknown;
  concurrency?: unknown;
  turn_limit?: unknown;
  run_cap_cents?: unknown;
  stuck_limit?: unknown;
};

export type HarnessPersonaRef = { id: string; name?: string };

export type HarnessRunIdentity = {
  when: string;
  runId: string;
  courseIds: string;
  childProfileIds: string;
  tutorModel: string;
  childModel: string;
  concurrency: string;
  turnLimit: string;
  costLimit: string;
  stuckLimit: string;
};

const EMPTY = "—";

export const HARNESS_RUN_IDENTITY_FIELDS: { key: keyof HarnessRunIdentity; label: string }[] = [
  { key: "when", label: "When" },
  { key: "runId", label: "Run id" },
  { key: "courseIds", label: "Course ids" },
  { key: "childProfileIds", label: "Child profile ids" },
  { key: "tutorModel", label: "Tutor model" },
  { key: "childModel", label: "Child model" },
  { key: "concurrency", label: "Concurrency" },
  { key: "turnLimit", label: "Turn limit" },
  { key: "costLimit", label: "Cost limit" },
  { key: "stuckLimit", label: "Stuck limit" },
];

function textList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item).trim()).filter(Boolean);
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/** Date and time in America/New_York, with the Eastern abbreviation. */
export function harnessRunWhen(iso: string | null | undefined): string {
  if (!iso) return EMPTY;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return EMPTY;
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(date);
}

function childProfileId(id: string, personas: HarnessPersonaRef[]): string {
  const persona = personas.find((item) => item.id === id);
  const name = text(persona?.name);
  if (!name || name === id) return id;
  return `${name} (${id})`;
}

function costLimit(value: unknown): string {
  if (value === null || value === undefined || value === "" || value === 0 || value === "0") return "blank";
  return `${value} cents`;
}

export function harnessRunIdentity(
  run: { id: string; created_at?: string | null; plan?: HarnessRunPlan | null },
  personas: HarnessPersonaRef[] = [],
): HarnessRunIdentity {
  const plan = run.plan ?? {};
  const tutorModels = textList(plan.tutor_models);
  const singleTutor = text(plan.tutor_model);
  if (tutorModels.length === 0 && singleTutor) tutorModels.push(singleTutor);
  return {
    when: harnessRunWhen(run.created_at),
    runId: run.id,
    courseIds: textList(plan.course_ids).join(", ") || EMPTY,
    childProfileIds: textList(plan.persona_ids).map((id) => childProfileId(id, personas)).join(", ") || EMPTY,
    tutorModel: tutorModels.join(", ") || EMPTY,
    childModel: text(plan.child_model) || EMPTY,
    concurrency: plan.concurrency === undefined || plan.concurrency === null ? EMPTY : String(plan.concurrency),
    turnLimit: plan.turn_limit === undefined || plan.turn_limit === null ? EMPTY : String(plan.turn_limit),
    costLimit: costLimit(plan.run_cap_cents),
    stuckLimit: plan.stuck_limit === undefined || plan.stuck_limit === null ? EMPTY : String(plan.stuck_limit),
  };
}
