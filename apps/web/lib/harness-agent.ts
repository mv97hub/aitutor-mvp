/** Plan and auth for the three harness calls an agent makes. No model call. */

import { timingSafeEqual, createHash } from "node:crypto";

import { ApiError } from "./api.ts";
import { clampConcurrency } from "./harness-background.ts";
import {
  DEFAULT_CHAT_CAP_CENTS,
  DEFAULT_CHILD_MODEL,
  DEFAULT_JUDGE_MODEL,
  DEFAULT_LUNA_TOKEN_CEILING,
  DEFAULT_STUCK_LIMIT,
} from "./harness.ts";

/** Chats in flight for an agent run. The runner still clamps at 8. */
export const AGENT_CONCURRENCY = 4;
export const AGENT_TUTOR_MODEL = "gpt-4.1";
export const AGENT_ITERATIONS = 1;
const STARTER_NUMBERS = 14;
const MAX_TURN_LIMIT = 500;
const MAX_COST_CENTS = 100_000_000;

export type CourseRef = { id: string; title?: string; code?: string; ready?: boolean };
export type PersonaRef = { id: string; name?: string; number?: number; archived?: boolean };

export type AgentJob = {
  course: string;
  personaSet: "starter" | Array<string | number>;
  turnLimit: number;
  costLimitCents: number;
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

function wholeNumber(value: unknown, label: string, max: number): number | string {
  if (typeof value !== "number" || !Number.isInteger(value)) return `${label} must be a whole number.`;
  if (value < 1 || value > max) return `${label} must be from 1 to ${max}.`;
  return value;
}

export function parseAgentJob(body: unknown): { job: AgentJob } | { detail: string } {
  if (!body || typeof body !== "object" || Array.isArray(body)) return { detail: "The request body must be an object." };
  const raw = body as Record<string, unknown>;
  const course = typeof raw.course === "string" ? raw.course.trim() : "";
  if (!course) return { detail: "Name a ready course." };
  let personaSet: AgentJob["personaSet"];
  if (raw.persona_set === "starter") {
    personaSet = "starter";
  } else if (Array.isArray(raw.persona_set) && raw.persona_set.length > 0) {
    const children: Array<string | number> = [];
    for (const item of raw.persona_set) {
      if (typeof item === "number" && Number.isInteger(item)) children.push(item);
      else if (typeof item === "string" && item.trim()) children.push(item.trim());
      else return { detail: "Each child in persona_set is a name or a number." };
    }
    personaSet = children;
  } else {
    return { detail: 'persona_set is "starter" or a list of children.' };
  }
  const turnLimit = wholeNumber(raw.turn_limit, "turn_limit", MAX_TURN_LIMIT);
  if (typeof turnLimit === "string") return { detail: turnLimit };
  const costLimit = wholeNumber(raw.cost_limit, "cost_limit", MAX_COST_CENTS);
  if (typeof costLimit === "string") return { detail: costLimit };
  return { job: { course, personaSet, turnLimit, costLimitCents: costLimit } };
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

export function agentRunPlan(courseId: string, personaIds: string[], job: AgentJob): Record<string, unknown> {
  return {
    persona_ids: personaIds,
    course_ids: [courseId],
    component_ids: [],
    tutor_models: [AGENT_TUTOR_MODEL],
    child_model: DEFAULT_CHILD_MODEL,
    judge_model: DEFAULT_JUDGE_MODEL,
    behavior: "rule",
    tutor_profile_ids: [],
    iterations: AGENT_ITERATIONS,
    chat_cap_cents: DEFAULT_CHAT_CAP_CENTS,
    run_cap_cents: job.costLimitCents,
    turn_limit: job.turnLimit,
    stuck_limit: DEFAULT_STUCK_LIMIT,
    stop_on_safety: false,
    concurrency: clampConcurrency(AGENT_CONCURRENCY),
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
    const course = selectCourse(courses, parsed.job.course);
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
    const created = await deps.createRun(agentRunPlan(course.id, selected.ids, parsed.job));
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
