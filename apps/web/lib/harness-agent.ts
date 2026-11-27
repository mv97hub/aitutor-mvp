/** Plan and auth for the three harness calls an agent makes. No model call. */

import { timingSafeEqual, createHash } from "node:crypto";

import { ApiError } from "./api.ts";
import { clampConcurrency } from "./harness-background.ts";
import {
  DEFAULT_CHAT_CAP_CENTS,
  DEFAULT_JUDGE_MODEL,
  DEFAULT_LUNA_TOKEN_CEILING,
} from "./harness.ts";
import { isKcModel, modelForCall } from "./kc-models.ts";

/** Recommended chats in flight. The runner still refuses more than 8. */
export const AGENT_CONCURRENCY = 4;
export const CONCURRENCY_CEILING = 8;
export const AGENT_ITERATIONS = 1;
/** Fields a create call may omit. concurrency then uses 4. judge_model uses gpt-6.1-sol. */
export const OPTIONAL_FIELDS = ["concurrency", "judge_model"] as const;
const STARTER_NUMBERS = 14;
const MAX_TURN_LIMIT = 500;
const MAX_STUCK_LIMIT = 500;
const MIN_STUCK_LIMIT = 2;
const MAX_COST_CENTS = 100_000_000;
const OPTIONAL_NOTE = "Optional fields: concurrency, judge_model.";

export type CourseRef = { id: string; title?: string; code?: string; ready?: boolean };
export type PersonaRef = { id: string; name?: string; number?: number; archived?: boolean };

export type AgentJob = {
  courses: string[];
  personaSet: "starter" | Array<string | number>;
  tutorModel: string;
  childModel: string;
  judgeModel: string;
  turnLimit: number;
  costLimitCents: number;
  stuckLimit: number;
  concurrency: number;
};

export type AgentDeps = {
  courses: () => Promise<CourseRef[]>;
  personas: () => Promise<PersonaRef[]>;
  ensureStarter: () => Promise<PersonaRef[]>;
  createRun: (plan: Record<string, unknown>) => Promise<{ id?: string }>;
  start: (id: string) => Promise<{ ok: boolean; status: number; text: string }>;
};

export function bearerToken(authorization: string | null): string {
  if (!authorization) return "";
  const match = /^Bearer\s+(\S+)\s*$/i.exec(authorization);
  return match?.[1] ?? "";
}

function digest(value: string): Buffer {
  return createHash("sha256").update(value).digest();
}

export function authorizeHarnessService(
  authorization: string | null,
  token: string | undefined,
): "ok" | "unconfigured" | "unauthorized" {
  const expected = (token ?? "").trim();
  if (!expected) return "unconfigured";
  const provided = bearerToken(authorization);
  if (!provided || !timingSafeEqual(digest(provided), digest(expected))) return "unauthorized";
  return "ok";
}

export function harnessAuthResponse(
  authorization: string | null,
  token: string | undefined = process.env.HARNESS_SERVICE_TOKEN,
): Response | null {
  const result = authorizeHarnessService(authorization, token);
  if (result === "ok") return null;
  if (result === "unconfigured") {
    return Response.json({ detail: "The harness service token is not configured." }, { status: 503 });
  }
  return Response.json({ detail: "A harness service token is required." }, { status: 401 });
}

function wholeNumber(value: unknown, label: string, min: number, max: number): number | string {
  if (typeof value !== "number" || !Number.isInteger(value)) return `${label} must be a whole number.`;
  if (value < min || value > max) return `${label} must be from ${min} to ${max}.`;
  return value;
}

function present(value: unknown): boolean {
  return value !== undefined && value !== null;
}

function textList(value: unknown): string[] | null {
  if (typeof value === "string" && value.trim()) return [value.trim()];
  if (!Array.isArray(value) || value.length === 0) return null;
  const names: string[] = [];
  for (const item of value) {
    if (typeof item !== "string" || !item.trim()) return null;
    names.push(item.trim());
  }
  return names;
}

function childList(value: unknown): AgentJob["personaSet"] | null {
  if (value === "starter") return "starter";
  if (!Array.isArray(value) || value.length === 0) return null;
  const children: Array<string | number> = [];
  for (const item of value) {
    if (typeof item === "number" && Number.isInteger(item)) children.push(item);
    else if (typeof item === "string" && item.trim()) children.push(item.trim());
    else return null;
  }
  return children;
}

function missingFields(names: string[]): string {
  const label = names.length === 1 ? "Missing required field" : "Missing required fields";
  return `${label}: ${names.join(", ")}. ${OPTIONAL_NOTE}`;
}

function chosenModel(value: unknown, label: string): string | { detail: string } {
  const text = typeof value === "string" ? value.trim() : "";
  const cleaned = text ? modelForCall(text) : "";
  if (!cleaned || !isKcModel(cleaned)) return { detail: `${label} must be one of the tutor models.` };
  return cleaned;
}

function blank(value: unknown): boolean {
  return !present(value) || (typeof value === "string" && !value.trim());
}

export function parseAgentJob(body: unknown): { job: AgentJob } | { detail: string } {
  if (!body || typeof body !== "object" || Array.isArray(body)) return { detail: "The request body must be an object." };
  const raw = body as Record<string, unknown>;
  const missing: string[] = [];
  let shape = "";
  let courses: string[] | null = null;
  if (blank(raw.courses) && blank(raw.course)) missing.push("courses");
  else {
    courses = textList(!blank(raw.courses) ? raw.courses : raw.course);
    if (!courses) shape = "courses is a list of ready courses.";
  }
  let profiles: AgentJob["personaSet"] | null = null;
  if (blank(raw.child_profiles) && blank(raw.persona_set)) missing.push("child_profiles");
  else {
    profiles = childList(!blank(raw.child_profiles) ? raw.child_profiles : raw.persona_set);
    if (!profiles && !shape) shape = 'child_profiles is "starter" or a list of test children.';
  }
  if (blank(raw.tutor_model)) missing.push("tutor_model");
  if (blank(raw.child_model)) missing.push("child_model");
  if (!present(raw.turn_limit)) missing.push("turn_limit");
  if (!present(raw.cost_limit)) missing.push("cost_limit");
  if (!present(raw.stuck_limit)) missing.push("stuck_limit");
  if (missing.length > 0 || shape) {
    const parts: string[] = [];
    if (missing.length === 1) parts.push(`Missing required field: ${missing[0]}.`);
    else if (missing.length > 1) parts.push(`Missing required fields: ${missing.join(", ")}.`);
    if (shape) parts.push(shape);
    if (missing.length > 0) parts.push(OPTIONAL_NOTE);
    return { detail: parts.join(" ") };
  }
  if (!courses || !profiles) return { detail: missingFields(["courses", "child_profiles"]) };
  const tutorModel = chosenModel(raw.tutor_model, "tutor_model");
  if (typeof tutorModel !== "string") return tutorModel;
  const childModel = chosenModel(raw.child_model, "child_model");
  if (typeof childModel !== "string") return childModel;
  const judgeSource = present(raw.judge_model) && !(typeof raw.judge_model === "string" && !raw.judge_model.trim())
    ? raw.judge_model
    : DEFAULT_JUDGE_MODEL;
  const judgeModel = chosenModel(judgeSource, "judge_model");
  if (typeof judgeModel !== "string") return judgeModel;
  const turnLimit = wholeNumber(raw.turn_limit, "turn_limit", 1, MAX_TURN_LIMIT);
  if (typeof turnLimit === "string") return { detail: turnLimit };
  const costLimit = wholeNumber(raw.cost_limit, "cost_limit", 1, MAX_COST_CENTS);
  if (typeof costLimit === "string") return { detail: costLimit };
  const stuckLimit = wholeNumber(raw.stuck_limit, "stuck_limit", MIN_STUCK_LIMIT, MAX_STUCK_LIMIT);
  if (typeof stuckLimit === "string") return { detail: stuckLimit };
  const concurrency = present(raw.concurrency)
    ? wholeNumber(raw.concurrency, "concurrency", 1, CONCURRENCY_CEILING)
    : AGENT_CONCURRENCY;
  if (typeof concurrency === "string") return { detail: `${concurrency} 4 is recommended.` };
  return {
    job: {
      courses,
      personaSet: profiles,
      tutorModel,
      childModel,
      judgeModel,
      turnLimit,
      costLimitCents: costLimit,
      stuckLimit,
      concurrency,
    },
  };
}

export function selectCourse(courses: CourseRef[], course: string): { id: string } | { detail: string } {
  const wanted = course.trim();
  if (!wanted) return { detail: "Name a ready course." };
  const ready = courses.filter((item) => item.ready === true);
  const same = (value: string | undefined) => (value || "").trim().toLowerCase() === wanted.toLowerCase();
  const byId = ready.find((item) => item.id === wanted);
  if (byId) return { id: byId.id };
  const byCode = ready.filter((item) => same(item.code));
  if (byCode.length === 1) return { id: byCode[0].id };
  if (byCode.length > 1) return { detail: "More than one ready course has that code. Pass the course id." };
  const byTitle = ready.filter((item) => same(item.title));
  if (byTitle.length === 1) return { id: byTitle[0].id };
  if (byTitle.length > 1) return { detail: "More than one ready course has that title. Pass the course id." };
  const any = courses.find((item) => item.id === wanted || same(item.title) || same(item.code));
  if (any && any.ready !== true) return { detail: "That course is not ready." };
  return { detail: "Choose a ready course." };
}

export function selectCourses(catalog: CourseRef[], wanted: string[]): { ids: string[] } | { detail: string } {
  const ids: string[] = [];
  for (const name of wanted) {
    const selected = selectCourse(catalog, name);
    if ("detail" in selected) {
      if (selected.detail === "That course is not ready.") return { detail: `${name} is not ready.` };
      if (selected.detail === "Choose a ready course.") return { detail: `${name} is not a ready course.` };
      return selected;
    }
    if (!ids.includes(selected.id)) ids.push(selected.id);
  }
  if (ids.length === 0) return { detail: "Name at least one ready course." };
  return { ids };
}

function starterMissing(personas: PersonaRef[]): boolean {
  const numbers = new Set(personas.map((persona) => Number(persona.number)));
  for (let number = 1; number <= STARTER_NUMBERS; number += 1) {
    if (!numbers.has(number)) return true;
  }
  return false;
}

export function selectPersonas(
  personas: PersonaRef[],
  personaSet: AgentJob["personaSet"],
): { ids: string[] } | { detail: string } | { needsStarter: true } {
  const listed = personas.filter((persona) => persona.archived !== true && persona.id);
  if (personaSet === "starter") {
    if (starterMissing(personas)) return { needsStarter: true };
    const starter = listed
      .filter((persona) => {
        const number = Number(persona.number);
        return number >= 1 && number <= STARTER_NUMBERS;
      })
      .sort((left, right) => Number(left.number) - Number(right.number));
    if (starter.length === 0) return { detail: "The starter children are archived." };
    return { ids: starter.map((persona) => persona.id) };
  }
  const ids: string[] = [];
  for (const item of personaSet) {
    const persona = listed.find((candidate) => {
      if (typeof item === "number") return Number(candidate.number) === item;
      if (/^\d+$/.test(item)) return Number(candidate.number) === Number(item) || candidate.name === item;
      return candidate.name === item;
    });
    if (!persona) {
      const label = typeof item === "number" ? `AI_Child${item}` : item;
      return { detail: `${label} is not a test child.` };
    }
    if (!ids.includes(persona.id)) ids.push(persona.id);
  }
  return { ids };
}

export function agentRunPlan(courseIds: string[], personaIds: string[], job: AgentJob): Record<string, unknown> {
  return {
    persona_ids: personaIds,
    course_ids: courseIds,
    component_ids: [],
    tutor_models: [job.tutorModel],
    child_model: job.childModel,
    judge_model: job.judgeModel,
    behavior: "rule",
    tutor_profile_ids: [],
    iterations: AGENT_ITERATIONS,
    chat_cap_cents: DEFAULT_CHAT_CAP_CENTS,
    run_cap_cents: job.costLimitCents,
    turn_limit: job.turnLimit,
    stuck_limit: job.stuckLimit,
    stop_on_safety: false,
    concurrency: clampConcurrency(job.concurrency),
    luna_token_ceiling: DEFAULT_LUNA_TOKEN_CEILING,
    script: [],
    seed: 0,
  };
}

function failureDetail(text: string, fallback: string): string {
  const trimmed = text.trim();
  if (!trimmed) return fallback;
  try {
    const parsed = JSON.parse(trimmed) as { detail?: unknown };
    if (typeof parsed.detail === "string" && parsed.detail.trim()) return parsed.detail.trim();
  } catch {
    // The start route returns plain text when the tutor service is down.
  }
  return trimmed;
}

export async function createAgentRun(
  body: unknown,
  deps: AgentDeps,
): Promise<{ status: number; body: Record<string, unknown> }> {
  const parsed = parseAgentJob(body);
  if ("detail" in parsed) return { status: 422, body: { detail: parsed.detail } };
  try {
    const [courses, firstPersonas] = await Promise.all([deps.courses(), deps.personas()]);
    const course = selectCourses(courses, parsed.job.courses);
    if ("detail" in course) return { status: 422, body: { detail: course.detail } };
    let personas = firstPersonas;
    let selected = selectPersonas(personas, parsed.job.personaSet);
    if ("needsStarter" in selected) {
      personas = await deps.ensureStarter();
      selected = selectPersonas(personas, parsed.job.personaSet);
    }
    if (!("ids" in selected)) {
      const detail = "detail" in selected ? selected.detail : "Add the starter children first.";
      return { status: 422, body: { detail } };
    }
    const created = await deps.createRun(agentRunPlan(course.ids, selected.ids, parsed.job));
    const id = typeof created.id === "string" ? created.id : "";
    if (!id) return { status: 502, body: { detail: "The run was saved, but it did not return an id." } };
    const started = await deps.start(id);
    if (!started.ok) {
      return {
        status: started.status,
        body: { detail: failureDetail(started.text, "The run was saved, but it did not start."), id },
      };
    }
    return { status: 201, body: { id } };
  } catch (error) {
    if (error instanceof ApiError) return { status: error.status, body: { detail: error.message } };
    const message = error instanceof Error ? error.message : "Could not start the run.";
    return { status: 502, body: { detail: message } };
  }
}
