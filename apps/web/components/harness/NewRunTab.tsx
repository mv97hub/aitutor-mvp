"use client";

import { useMemo, useState } from "react";

import type { HarnessPersona } from "@/components/harness/ProfilesView";
import {
  DEFAULT_CHAT_CAP_CENTS,
  DEFAULT_CHILD_MODEL,
  DEFAULT_CONCURRENCY,
  DEFAULT_JUDGE_MODEL,
  DEFAULT_LUNA_TOKEN_CEILING,
  DEFAULT_STUCK_LIMIT,
  DEFAULT_TURN_LIMIT,
  HARNESS_MODELS,
  chatCount,
  estimateChatUsd,
  listedTestChildren,
  lunaNote,
  sameModelWarning,
} from "@/lib/harness";
import { findHarnessScenario, SCENARIO_GROUPS } from "@/lib/harness-scenarios";
import { kcModelLabel } from "@/lib/kc-models";
import { api } from "@/lib/api";
import type { KcCourse } from "@/lib/kc";
import type { TutorProfile } from "@/lib/types";

type Plan = {
  persona_ids: string[];
  course_ids: string[];
  component_ids: string[];
  tutor_models: string[];
  child_model: string;
  judge_model: string;
  behavior: "rule" | "free" | "script";
  tutor_profile_ids: string[];
  iterations: number;
  chat_cap_cents: number;
  run_cap_cents: string;
  turn_limit: number;
  stuck_limit: number;
  stop_on_safety: boolean;
  concurrency: number;
  luna_token_ceiling: number;
  script: string;
  scenario: string;
  seed: string;
  pair_tutor_seeds: boolean;
};

export function NewRunTab({
  personas,
  courses,
  profiles,
  onStarted,
}: {
  personas: HarnessPersona[];
  courses: KcCourse[];
  profiles: TutorProfile[];
  onStarted: (runId: string) => void;
}) {
  const ready = courses.filter((course) => course.ready);
  const [plan, setPlan] = useState<Plan>({
    persona_ids: [],
    course_ids: [],
    component_ids: [],
    tutor_models: ["gpt-4.1"],
    child_model: DEFAULT_CHILD_MODEL,
    judge_model: DEFAULT_JUDGE_MODEL,
    behavior: "rule",
    tutor_profile_ids: [],
    iterations: 3,
    chat_cap_cents: DEFAULT_CHAT_CAP_CENTS,
    run_cap_cents: "",
    turn_limit: DEFAULT_TURN_LIMIT,
    stuck_limit: DEFAULT_STUCK_LIMIT,
    stop_on_safety: false,
    concurrency: DEFAULT_CONCURRENCY,
    luna_token_ceiling: DEFAULT_LUNA_TOKEN_CEILING,
    script: "",
    scenario: "",
    seed: "",
    pair_tutor_seeds: false,
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const children = listedTestChildren(personas);
  const scenario = plan.behavior === "script" ? findHarnessScenario(plan.scenario) : undefined;
  const seedInvalid = plan.seed !== "" && (!/^\d+$/.test(plan.seed) || !Number.isSafeInteger(Number(plan.seed)) || Number(plan.seed) < 1);
  const components = ready
    .filter((course) => plan.course_ids.includes(course.id))
    .flatMap((course) => course.components.map((component) => ({ ...component, courseId: course.id, courseTitle: course.title })));
  const componentCount =
    plan.component_ids.length > 0 ? plan.component_ids.length : plan.course_ids.length > 0 ? components.length : 0;
  const count = chatCount({
    children: plan.persona_ids.length,
    components: componentCount,
    models: plan.tutor_models.length,
    profiles: Math.max(1, plan.tutor_profile_ids.length),
    iterations: plan.iterations,
  });
  const estimate = useMemo(() => {
    const tutor = plan.tutor_models[0] || "gpt-4.1";
    return estimateChatUsd(tutor, plan.child_model, plan.judge_model);
  }, [plan.tutor_models, plan.child_model, plan.judge_model]);
  const boundary = personas.some(
    (persona) => plan.persona_ids.includes(persona.id) && (persona.name === "AI_Child12" || Number(persona.traits.boundary) >= 4),
  );

  function toggle(list: string[], id: string): string[] {
    return list.includes(id) ? list.filter((item) => item !== id) : [...list, id];
  }

  function chooseScenario(id: string) {
    const selected = findHarnessScenario(id);
    const allowed = children.filter(persona => selected?.group.personas.includes(persona.number)).map(persona => persona.id);
    const previous = plan.persona_ids.filter(personaId => allowed.includes(personaId));
    setPlan({
      ...plan,
      scenario: id,
      persona_ids: selected ? (previous.length ? previous : allowed) : plan.persona_ids,
    });
  }

  async function loadFixture() {
    setError("");
    try {
      await api("/kc/harness/fixture", { method: "POST" });
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the fixture course.");
    }
  }

  async function start() {
    setBusy(true);
    setError("");
    try {
      const created = await api<{ id: string }>("/kc/harness/runs", {
        method: "POST",
        body: JSON.stringify({
          ...plan,
          run_cap_cents: plan.run_cap_cents.trim() ? Number(plan.run_cap_cents) : null,
          scenario: scenario?.variant.id || "",
          scenario_group: scenario?.group.id || "",
          seed: Number(plan.seed) || 0,
          script: plan.behavior === "script" && !scenario ? plan.script.split("\n").map((line) => line.trim()).filter(Boolean) : [],
          stop_on_safety: plan.stop_on_safety,
        }),
      });
      const started = await fetch(`/api/kc/harness/runs/${created.id}/start`, { method: "POST" });
      if (!started.ok) {
        setError((await started.text()) || "The run was saved, but it did not start.");
      }
      onStarted(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the run.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="harness-panel">
      <h2>New run</h2>
      <p className="help">
        {plan.persona_ids.length} children × {componentCount} components × {plan.tutor_models.length} models ×{" "}
        {Math.max(1, plan.tutor_profile_ids.length)} profiles × {plan.iterations} iterations = {count} {count === 1 ? "chat" : "chats"}.
      </p>
      {estimate.usd ? (
        <p className="help">
          Rough estimate about ${Number(estimate.usd).toFixed(2)} per chat before a run has been measured.{" "}
          {estimate.unpriced.length > 0 ? lunaNote(estimate.unpriced[0]) : "Priced models only."}
        </p>
      ) : (
        <p className="help">{lunaNote("gpt-6-luna")}</p>
      )}
      {sameModelWarning(plan.child_model, plan.tutor_models) ? (
        <p className="banner">The child model and the tutor model are the same. A model talking to itself tends to be agreeable.</p>
      ) : null}
      {error ? <p className="banner">{error}</p> : null}
      <div className="harness-two">
        <fieldset>
          <legend>Test children</legend>
          {children.map((persona) => (
            <label key={persona.id}>
              <input
                type="checkbox"
                checked={plan.persona_ids.includes(persona.id)}
                disabled={Boolean(scenario && !scenario.group.personas.includes(persona.number))}
                onChange={() => setPlan({ ...plan, persona_ids: toggle(plan.persona_ids, persona.id) })}
              />
              {persona.name} · {persona.description}
            </label>
          ))}
        </fieldset>
        <fieldset>
          <legend>Courses and components</legend>
          <button type="button" onClick={() => void loadFixture()}>
            Load fixture courses
          </button>
          {ready.map((course) => (
            <label key={course.id}>
              <input
                type="checkbox"
                checked={plan.course_ids.includes(course.id)}
                onChange={() => setPlan({ ...plan, course_ids: toggle(plan.course_ids, course.id) })}
              />
              {course.title}
              {course.code === "harness-every-block" ? " (every block type)" : ""}
            </label>
          ))}
          {components.map((component) => (
            <label key={component.id}>
              <input
                type="checkbox"
                checked={plan.component_ids.includes(component.id)}
                onChange={() => setPlan({ ...plan, component_ids: toggle(plan.component_ids, component.id) })}
              />
              {component.courseTitle}: {component.title}
            </label>
          ))}
        </fieldset>
      </div>
      <div className="harness-two">
        <fieldset>
          <legend>Tutor model</legend>
          {HARNESS_MODELS.map((model) => (
            <label key={model}>
              <input
                type="checkbox"
                checked={plan.tutor_models.includes(model)}
                onChange={() => setPlan({ ...plan, tutor_models: toggle(plan.tutor_models, model) })}
              />
              {kcModelLabel(model)}
            </label>
          ))}
        </fieldset>
        <div>
          <label>
            Child model
            <select value={plan.child_model} onChange={(event) => setPlan({ ...plan, child_model: event.target.value })}>
              {HARNESS_MODELS.map((model) => (
                <option key={model} value={model}>
                  {kcModelLabel(model)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Judge model
            <select value={plan.judge_model} onChange={(event) => setPlan({ ...plan, judge_model: event.target.value })}>
              {HARNESS_MODELS.map((model) => (
                <option key={model} value={model}>
                  {kcModelLabel(model)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Child behavior
            <select
              value={plan.behavior}
              onChange={(event) => setPlan({ ...plan, behavior: event.target.value as Plan["behavior"], scenario: "" })}
            >
              <option value="rule">Rule-led</option>
              <option value="free">Free play</option>
              <option value="script">Script</option>
            </select>
          </label>
          <label>
            Tutor profile
            <select
              value={plan.tutor_profile_ids[0] || ""}
              onChange={(event) => setPlan({ ...plan, tutor_profile_ids: event.target.value ? [event.target.value] : [] })}
            >
              <option value="">Default profile</option>
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      <div className="harness-grid">
        <label>
          Iterations
          <input type="number" min={1} max={50} value={plan.iterations} onChange={(event) => setPlan({ ...plan, iterations: Number(event.target.value) })} />
        </label>
        <label>
          Run seed (optional)
          <input type="number" min={1} step={1} value={plan.seed} aria-invalid={seedInvalid} onChange={(event) => setPlan({ ...plan, seed: event.target.value })} />
        </label>
        <label>
          <input type="checkbox" checked={plan.pair_tutor_seeds} onChange={(event) => setPlan({ ...plan, pair_tutor_seeds: event.target.checked })} />
          Pair learner draws across tutors or scenario variants
        </label>
        <label>
          Spending cap per chat (cents)
          <input type="number" min={1} value={plan.chat_cap_cents} onChange={(event) => setPlan({ ...plan, chat_cap_cents: Number(event.target.value) })} />
        </label>
        <label>
          Run cap (cents, blank for none)
          <input value={plan.run_cap_cents} onChange={(event) => setPlan({ ...plan, run_cap_cents: event.target.value })} />
        </label>
        <label>
          Luna token ceiling
          <input type="number" min={1000} value={plan.luna_token_ceiling} onChange={(event) => setPlan({ ...plan, luna_token_ceiling: Number(event.target.value) })} />
        </label>
        <label>
          Turn limit
          <input type="number" min={1} value={plan.turn_limit} onChange={(event) => setPlan({ ...plan, turn_limit: Number(event.target.value) })} />
        </label>
        <label>
          Stuck limit
          <input type="number" min={2} value={plan.stuck_limit} onChange={(event) => setPlan({ ...plan, stuck_limit: Number(event.target.value) })} />
        </label>
        <label>
          Concurrency
          <input type="number" min={1} max={8} value={plan.concurrency} onChange={(event) => setPlan({ ...plan, concurrency: Number(event.target.value) })} />
        </label>
        <label>
          <input
            type="checkbox"
            checked={plan.stop_on_safety}
            onChange={(event) => setPlan({ ...plan, stop_on_safety: event.target.checked })}
          />
          Stop on the first safety flag
        </label>
      </div>
      <p className="help">
        Cap {plan.chat_cap_cents} cents per chat. Luna calls are not part of that cap. Token ceiling {plan.luna_token_ceiling}.{" "}
        {boundary ? "AI_Child12 is included, so mild scripted probes are on. Those flags stay out of the AI Safety queue." : ""}
      </p>
      {seedInvalid ? <p className="banner">Enter a positive whole-number seed or leave it blank to generate one.</p> : null}
      {plan.pair_tutor_seeds ? <p className="help">For paired runs, use the same run seed, scenario family, children, components and iterations. A blank seed generates a new value for each run.</p> : null}
      {plan.behavior === "script" ? (
        <fieldset>
          <legend>Scripted scenario</legend>
          <label>
            Scenario
            <select value={plan.scenario} onChange={(event) => chooseScenario(event.target.value)}>
              <option value="">Custom script</option>
              {SCENARIO_GROUPS.map(group => (
                <optgroup key={group.id} label={group.label}>
                  {group.variants.map(variant => <option key={variant.id} value={variant.id}>{variant.label}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          {scenario ? (
            <>
              <p>{scenario.group.context}</p>
              <p className="help">
                {scenario.group.personas.map(n => `AI_Child${n}`).join(", ")} · Supported blocks: {scenario.group.blockTypes.join(", ")}.
                {" "}Under “Harness fixture · learner scenarios”, choose {scenario.group.fixture}. Use “Load fixture courses” if the course is missing.
                {" "}Other turns use ordinary learner behavior. The report counts when the scripted response is sent.
              </p>
            </>
          ) : (
            <label>
              Custom script, one child line per row
              <textarea value={plan.script} onChange={(event) => setPlan({ ...plan, script: event.target.value })} rows={4} />
            </label>
          )}
        </fieldset>
      ) : null}
      <button type="button" disabled={busy || count < 1 || seedInvalid} onClick={() => void start()}>
        {busy ? "Starting…" : `Start ${count} ${count === 1 ? "chat" : "chats"}`}
      </button>
    </section>
  );
}
