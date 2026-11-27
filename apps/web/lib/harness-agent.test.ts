import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { clampConcurrency } from "./harness-background.ts";
import {
  AGENT_CONCURRENCY,
  agentRunPlan,
  authorizeHarnessService,
  createAgentRun,
  harnessAuthResponse,
  parseAgentJob,
  selectCourse,
  selectPersonas,
  type AgentDeps,
  type CourseRef,
  type PersonaRef,
} from "./harness-agent.ts";

const courses: CourseRef[] = [
  { id: "course-1", title: "Costs of Inflation", code: "inflation", ready: true },
  { id: "course-2", title: "Draft", code: "draft", ready: false },
];

const personas: PersonaRef[] = [
  { id: "p2", name: "AI_Child2", number: 2 },
  { id: "p1", name: "AI_Child1", number: 1 },
  { id: "old", name: "AI_Child3", number: 3, archived: true },
];

function starterPersonas(): PersonaRef[] {
  return Array.from({ length: 14 }, (_, index) => ({
    id: `p${index + 1}`,
    name: `AI_Child${index + 1}`,
    number: index + 1,
  }));
}

test("the service token is a bearer token, not a browser session", () => {
  assert.equal(authorizeHarnessService(null, ""), "unconfigured");
  assert.equal(authorizeHarnessService("Bearer secret", ""), "unconfigured");
  assert.equal(authorizeHarnessService(null, "secret"), "unauthorized");
  assert.equal(authorizeHarnessService("Bearer wrong", "secret"), "unauthorized");
  assert.equal(authorizeHarnessService("Bearer secret", "secret"), "ok");
  assert.equal(authorizeHarnessService("bearer secret", "secret"), "ok");
  const denied = harnessAuthResponse("Bearer no", "secret");
  assert.equal(denied?.status, 401);
  const missing = harnessAuthResponse("Bearer secret", "  ");
  assert.equal(missing?.status, 503);
});

test("an agent run is concurrency 4 and the ceiling stays 8", () => {
  assert.equal(AGENT_CONCURRENCY, 4);
  assert.equal(clampConcurrency(AGENT_CONCURRENCY), 4);
  assert.equal(clampConcurrency(8), 8);
  assert.equal(clampConcurrency(9), 8);
  const plan = agentRunPlan("course-1", ["p1"], {
    course: "Costs of Inflation",
    personaSet: "starter",
    turnLimit: 12,
    costLimitCents: 80,
  });
  assert.equal(plan.concurrency, 4);
  assert.equal(plan.turn_limit, 12);
  assert.equal(plan.run_cap_cents, 80);
  assert.equal(plan.chat_cap_cents, 40);
  assert.equal(plan.iterations, 1);
  assert.deepEqual(plan.course_ids, ["course-1"]);
  assert.deepEqual(plan.persona_ids, ["p1"]);
});

test("the job body is course, persona set, turn limit, and cost limit", () => {
  const parsed = parseAgentJob({
    course: " Costs of Inflation ",
    persona_set: ["AI_Child1", 13],
    turn_limit: 40,
    cost_limit: 400,
  });
  assert.deepEqual(parsed, {
    job: { course: "Costs of Inflation", personaSet: ["AI_Child1", 13], turnLimit: 40, costLimitCents: 400 },
  });
  assert.equal("detail" in parseAgentJob({ course: "Inflation", persona_set: "starter" }), true);
  assert.equal("detail" in parseAgentJob({ course: "Inflation", persona_set: "starter", turn_limit: 1.5, cost_limit: 10 }), true);
  assert.equal(selectCourse(courses, "costs of inflation").id, "course-1");
  assert.equal(selectCourse(courses, "inflation").id, "course-1");
  assert.equal(selectCourse(courses, "course-1").id, "course-1");
  assert.equal("detail" in selectCourse(courses, "Draft"), true);
  assert.deepEqual(selectPersonas(personas, ["AI_Child1", "2"]), { ids: ["p1", "p2"] });
  assert.equal("detail" in selectPersonas(personas, ["AI_Child3"]), true);
  assert.equal("needsStarter" in selectPersonas(personas, "starter"), true);
  assert.deepEqual(selectPersonas(starterPersonas(), "starter").ids, starterPersonas().map((persona) => persona.id));
});

test("create stores the run, starts it, and returns the id", async () => {
  let started = "";
  const deps: AgentDeps = {
    courses: async () => courses,
    personas: async () => starterPersonas(),
    ensureStarter: async () => {
      throw new Error("starter is already stored");
    },
    createRun: async () => ({ id: "run-1" }),
    start: async (id) => {
      started = id;
      return { ok: true, status: 200, text: '{"ok":true,"running":true}' };
    },
  };
  const result = await createAgentRun(
    { course: "Costs of Inflation", persona_set: "starter", turn_limit: 40, cost_limit: 400 },
    deps,
  );
  assert.equal(result.status, 201);
  assert.deepEqual(result.body, { id: "run-1" });
  assert.equal(started, "run-1");
});

test("a missing starter set is created before the run starts", async () => {
  let ensured = false;
  const deps: AgentDeps = {
    courses: async () => courses,
    personas: async () => (ensured ? starterPersonas() : []),
    ensureStarter: async () => {
      ensured = true;
      return starterPersonas();
    },
    createRun: async (plan) => {
      assert.equal((plan.persona_ids as string[]).length, 14);
      return { id: "run-2" };
    },
    start: async () => ({ ok: true, status: 200, text: "" }),
  };
  const result = await createAgentRun(
    { course: "course-1", persona_set: "starter", turn_limit: 8, cost_limit: 50 },
    deps,
  );
  assert.equal(result.status, 201);
  assert.equal(ensured, true);
});

test("a start failure still returns the run id and does not look created-only", async () => {
  const deps: AgentDeps = {
    courses: async () => courses,
    personas: async () => [{ id: "p1", name: "AI_Child1", number: 1 }],
    ensureStarter: async () => [],
    createRun: async () => ({ id: "run-3" }),
    start: async () => ({ ok: false, status: 502, text: "Could not start the run." }),
  };
  const result = await createAgentRun(
    { course: "inflation", persona_set: [1], turn_limit: 5, cost_limit: 20 },
    deps,
  );
  assert.equal(result.status, 502);
  assert.equal(result.body.id, "run-3");
  assert.match(String(result.body.detail), /Could not start/);
});

test("the three agent routes require the token and the page start route does not", () => {
  const root = new URL("../app/api/kc/harness/", import.meta.url);
  for (const path of ["agent/runs/route.ts", "agent/runs/[id]/route.ts", "agent/runs/[id]/download/route.ts"]) {
    const source = readFileSync(new URL(path, root), "utf8");
    assert.match(source, /harnessAuthResponse/);
  }
  const start = readFileSync(new URL("./harness-start.ts", import.meta.url), "utf8");
  assert.match(start, /launchBackgroundRun/);
  assert.match(start, /\/claim/);
  assert.doesNotMatch(start, /harnessAuthResponse/);
  const pageStart = readFileSync(new URL("runs/[id]/start/route.ts", root), "utf8");
  assert.match(pageStart, /startStoredRun/);
  assert.doesNotMatch(pageStart, /harnessAuthResponse/);
  const download = readFileSync(new URL("agent/runs/[id]/download/route.ts", root), "utf8");
  assert.match(download, /\/kc\/harness\/runs\/\$\{id\}\/download/);
  const read = readFileSync(new URL("agent/runs/[id]/route.ts", root), "utf8");
  assert.match(read, /\/kc\/harness\/runs\/\$\{id\}\/agent/);
});

test("the documentation index links the harness agent page", () => {
  const index = readFileSync(new URL("../app/documentation/page.tsx", import.meta.url), "utf8");
  assert.match(index, /\/documentation\/harness-agent/);
  assert.match(index, /Harness agent/);
  const page = readFileSync(new URL("../app/documentation/harness-agent/page.tsx", import.meta.url), "utf8");
  assert.match(page, /POST \/api\/kc\/harness\/agent\/runs/);
  assert.match(page, /GET \/api\/kc\/harness\/agent\/runs\/\{id\}/);
  assert.match(page, /GET \/api\/kc\/harness\/agent\/runs\/\{id\}\/download/);
  assert.match(page, /Authorization: Bearer/);
  assert.match(page, /persona_set/);
  assert.match(page, /turn_limit/);
  assert.match(page, /cost_limit/);
  assert.match(page, /status/);
  assert.match(page, /stopped/);
  assert.match(page, /one row per child/);
});
