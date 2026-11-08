/** Form state for the KC Prompt Tester. The API calls build_kc_prompt. */

import { LAYER_FIELDS, LAYER_HEADINGS, type LayerField } from "./kc-layer-fields.ts";
import { BLOCK_LABELS, BLOCK_TYPES } from "./kc-blocks.ts";
import { AUDIENCES, KINDS, type KcComponent, type KcCourse } from "./kc.ts";
import type { Student, TutorProfile } from "./types.ts";

export { LAYER_HEADINGS };

export const READ_ONLY_DERIVED = [
  "Move name",
  "Evidence",
  "Effective struggle window",
  "Effective enrichment",
  "Asks why",
] as const;

export const DEFAULT_TUTOR_PROFILE: TutorProfile = {
  instructive: 3,
  persona: "curious-co-explorer",
  lexicon: "middle-grade-vivid",
  voice_override: false,
  metaphors: "playground-sports",
  sidekick: "bumbling-partner",
  struggle_window: "standard",
  anti_spoiler: true,
  one_question: true,
  use_interests: true,
  stay_on_course: true,
  growth_praise: true,
  misconception_policy: "retry_once",
  self_explanation: true,
  enrichment: "on_request",
};

const YES_NO = new Set([
  "Use interests",
  "Stay on course",
  "Anti-spoiler",
  "One question",
  "Growth-mindset praise",
  "Self-explanation",
  "Choice widget",
  "Help requested",
  "Redirect pending",
  "Unit close",
  "Course outro",
]);

const TEXT_AREAS = new Set([
  "Course description",
  "Component description",
  "Core truth",
  "Rubric lines",
  "Misconceptions",
  "Transfer case",
  "Counterfactual",
  "Last answer",
  "Last four messages",
  "Prerequisite status",
]);

const NUMBER_FIELDS = new Set([
  "Minutes",
  "Age",
  "Move index",
  "Attempts on this move",
  "Minutes used",
  "Reveals used",
  "Off-course count",
  "Enrichment turns",
]);

const UNIT_FIELDS = [
  "Component title",
  "Component code",
  "Component description",
  "Type",
  "Core truth",
  "Rubric lines",
  "Misconceptions",
  "Prerequisite codes",
  "Encompass codes",
  "Transfer case",
  "Counterfactual",
  "Prerequisite status",
  "Course position",
] as const;

export const FIELD_OPTIONS: Record<string, readonly (readonly [string, string])[]> = {
  Audience: AUDIENCES.map((band) => [band, band] as const),
  Kind: KINDS.map((kind) => [kind.id, kind.label] as const),
  Type: [["", "Unset"], ...BLOCK_TYPES.map((type) => [type, BLOCK_LABELS[type]] as const)],
  Persona: [
    ["curious-co-explorer", "Curious co-explorer"],
    ["tactical-coach", "Tactical coach"],
    ["debate-moderator", "Debate moderator"],
    ["patient-explainer", "Patient explainer"],
  ],
  Lexicon: [
    ["early-concrete", "Early concrete"],
    ["middle-grade-vivid", "Middle-grade vivid"],
    ["precise-visual", "Precise visual"],
    ["analytical-high-school", "Analytical high-school"],
  ],
  Metaphors: [
    ["playground-sports", "Playground and sports"],
    ["buildings-machines", "Buildings and machines"],
    ["policy-cause", "Policy and cause-and-effect"],
    ["none", "None (plain language only)"],
  ],
  Sidekick: [
    ["bumbling-partner", "Bumbling partner"],
    ["rookie-picture", "Rookie who trusts a picture"],
    ["pundit", "Pundit who skips the chain"],
    ["off", "Off"],
  ],
  Instructive: [
    ["1", "1. Open on the question."],
    ["2", "2. One short line, then the question."],
    ["3", "3. Name the goal, then ask."],
    ["4", "4. Explain the idea, then ask."],
    ["5", "5. Teach a little more, then ask."],
  ],
  "Struggle window": [
    ["short", "Minimum"],
    ["standard", "Standard"],
    ["long", "Wide"],
  ],
  Enrichment: [
    ["direct", "Direct"],
    ["on_request", "On request"],
    ["offer", "Offer"],
  ],
  "Misconception policy": [["retry_once", "Retry once"]],
  "Support band": [
    ["ready", "Ready"],
    ["stretch", "Stretch"],
    ["hold", "Hold"],
  ],
  "Hint tier already given": [
    ["nudge", "Nudge"],
    ["analogy", "Analogy"],
    ["scaffold", "Scaffold"],
    ["reveal", "Reveal"],
  ],
  Affect: [
    ["", "Unset"],
    ["engaged", "Engaged"],
    ["stuck", "Stuck"],
    ["guessing", "Guessing"],
    ["frustrated", "Frustrated"],
  ],
  "Component status": [
    ["unknown", "Unknown"],
    ["fragile", "Fragile"],
    ["known", "Known"],
  ],
};

export type TesterValues = Record<string, string>;

export type PromptTesterRequest = {
  course_title: string;
  course_description: string;
  audience: string;
  kind: string;
  minutes: number | null;
  component_title: string;
  component_code: string;
  component_description: string;
  kc_type: string;
  core_truth: string;
  rubric: string[];
  misconceptions: { wrong_move: string; broken_kc: string }[];
  prerequisite_codes: string[];
  encompasses_codes: string[];
  transfer_case: string;
  counterfactual: string;
  type_fields: Record<string, unknown>;
  move_index: number;
  choice_on_screen: string;
  prerequisite_status: string;
  course_position: string;
  display_name: string;
  age: number | null;
  reading_level: string;
  modality: string;
  interests: string[];
  attempts: number;
  hint_tier: string;
  component_status: string;
  stability: string;
  last_answer: string;
  last_misconception: string;
  minutes_used: number;
  support_band: string;
  persona: string;
  lexicon: string;
  metaphors: string;
  sidekick: string;
  use_interests: string;
  instructive: number;
  struggle_window: string;
  stay_on_course: string;
  anti_spoiler: string;
  one_question: string;
  misconception_policy: string;
  enrichment: string;
  growth_praise: string;
  self_explanation: string;
  reveals: number;
  off_course_count: number;
  rubric_met: string[];
  last_messages: string;
  affect: string;
  help_requested: string;
  last_practiced: string;
  redirect_pending: string;
  enrichment_turns: number;
  unit_close: string;
  course_outro: string;
};

export type PromptTesterResult = {
  system_prompt: string;
  move_name: string;
  evidence: string;
  effective_struggle_window: string;
  effective_enrichment: string;
  asks_why: string;
};

export type TesterUnit = {
  id: string;
  label: string;
  patch: boolean;
  component: KcComponent;
};

export function formFields(): LayerField[] {
  return LAYER_FIELDS.filter((field) => field.name !== "Model");
}

export function fieldsForLayer(layer: string): LayerField[] {
  return formFields().filter((field) => field.layer === layer);
}

export function isReadOnly(name: string): boolean {
  return (READ_ONLY_DERIVED as readonly string[]).includes(name);
}

export function isYesNo(name: string): boolean {
  return YES_NO.has(name);
}

export function isTextArea(name: string): boolean {
  return TEXT_AREAS.has(name);
}

export function isNumber(name: string): boolean {
  return NUMBER_FIELDS.has(name);
}

export function courseLabel(course: { title: string; ready: boolean }): string {
  return course.ready ? course.title : `${course.title} (draft)`;
}

export function unitsFor(course: KcCourse): TesterUnit[] {
  const targets = course.components.map((component) => ({
    id: component.id,
    label: component.title,
    patch: false,
    component,
  }));
  const patches = course.patches.map((component) => ({
    id: component.id,
    label: `${component.title} (patch)`,
    patch: true,
    component,
  }));
  return [...targets, ...patches];
}

const LEGACY_BLOCK: Record<string, string> = {
  factual: "retrieval_check",
  procedural: "worked_example",
  conceptual: "case_study",
  causal: "spot_the_flaw",
  synthesis: "teach_back",
};

export function choiceForMove(blockType: string, _moveIndex: number): "yes" | "no" {
  if (blockType === "mcq" || blockType === "case_study") return "yes";
  return "no";
}

export function coursePosition(course: KcCourse, unitId: string): string {
  if (course.patches.some((item) => item.id === unitId)) return "Patch";
  const index = course.components.findIndex((item) => item.id === unitId);
  if (index < 0) return "";
  const previous = index > 0 ? course.components[index - 1]?.title ?? "" : "";
  const next = index + 1 < course.components.length ? course.components[index + 1]?.title ?? "" : "";
  return `${index + 1} of ${course.components.length}; previous: ${previous || "none"}; next: ${next || "none"}`;
}

export function prerequisiteStatus(codes: string[]): string {
  return codes.map((code) => code.trim()).filter(Boolean).map((code) => `${code}: unknown`).join("; ");
}

function yesNo(value: boolean | undefined, fallback = true): "yes" | "no" {
  if (value === undefined) return fallback ? "yes" : "no";
  return value ? "yes" : "no";
}

export function emptyTesterValues(profile: TutorProfile = DEFAULT_TUTOR_PROFILE): TesterValues {
  const values: TesterValues = {};
  for (const field of formFields()) values[field.name] = "";
  return {
    ...values,
    Audience: "9-11",
    Kind: "mastery",
    "Move index": "1",
    "Choice widget": "no",
    "Attempts on this move": "0",
    "Hint tier already given": "nudge",
    "Component status": "unknown",
    Stability: "0",
    "Minutes used": "0",
    "Support band": "ready",
    Persona: profile.persona,
    Lexicon: profile.lexicon,
    Metaphors: profile.metaphors,
    Sidekick: profile.sidekick,
    "Use interests": yesNo(profile.use_interests),
    Instructive: String(profile.instructive || 3),
    "Struggle window": profile.struggle_window || "standard",
    "Stay on course": yesNo(profile.stay_on_course),
    "Anti-spoiler": yesNo(profile.anti_spoiler),
    "One question": yesNo(profile.one_question),
    "Misconception policy": profile.misconception_policy || "retry_once",
    Enrichment: profile.enrichment || "on_request",
    "Growth-mindset praise": yesNo(profile.growth_praise),
    "Self-explanation": yesNo(profile.self_explanation),
    "Reveals used": "0",
    "Off-course count": "0",
    Affect: "",
    "Help requested": "no",
    "Redirect pending": "no",
    "Enrichment turns": "0",
    "Unit close": "no",
    "Course outro": "no",
  };
}

export function selectCourse(values: TesterValues, course: KcCourse): TesterValues {
  const next: TesterValues = {
    ...values,
    "Course title": course.title,
    "Course description": course.description ?? "",
    Audience: course.audience,
    Kind: course.kind,
    Minutes: course.minutes == null ? "" : String(course.minutes),
  };
  for (const name of UNIT_FIELDS) next[name] = "";
  next["Choice widget"] = "no";
  return next;
}

export function applyChild(values: TesterValues, child: Student): TesterValues {
  return {
    ...values,
    "Display name": child.display_name ?? "",
    Age: child.age == null ? "" : String(child.age),
    "Reading level": child.reading_level ?? "",
    Modality: child.modality ?? "",
    Interests: (child.interests ?? []).join(", "),
  };
}

export function applyUnit(values: TesterValues, course: KcCourse, unit: KcComponent): TesterValues {
  const fields = unit.type_fields ?? {};
  const moveIndex = Number(values["Move index"] || "1");
  return {
    ...values,
    "Course title": course.title,
    "Course description": course.description ?? "",
    Audience: course.audience,
    Kind: course.kind,
    Minutes: course.minutes == null ? "" : String(course.minutes),
    "Component title": unit.title,
    "Component code": unit.code,
    "Component description": unit.description ?? "",
    Type: unit.blocks?.find((block) => block.type)?.type ?? LEGACY_BLOCK[unit.kc_type ?? ""] ?? unit.kc_type ?? "",
    "Core truth": unit.core_truth ?? "",
    "Rubric lines": (unit.rubric ?? []).join("\n"),
    Misconceptions: (unit.misconceptions ?? [])
      .map((item) => `${item.wrong_move} -> ${item.broken_kc}`)
      .join("\n"),
    "Prerequisite codes": (unit.prerequisite_codes ?? []).join(", "),
    "Encompass codes": (unit.encompasses_codes ?? []).join(", "),
    "Transfer case": String(fields.transfer_case ?? ""),
    Counterfactual: String(fields.counterfactual ?? ""),
    "Prerequisite status": prerequisiteStatus(unit.prerequisite_codes ?? []),
    "Course position": coursePosition(course, unit.id),
    "Choice widget": choiceForMove(
      unit.blocks?.find((block) => block.type)?.type ?? LEGACY_BLOCK[unit.kc_type ?? ""] ?? unit.kc_type ?? "",
      Number.isFinite(moveIndex) ? moveIndex : 1,
    ),
  };
}

function lines(value: string): string[] {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

function pieces(value: string): string[] {
  return value.split(/[\n,]/).map((item) => item.trim()).filter(Boolean);
}

function whole(value: string, fallback: number): number {
  if (!value.trim()) return fallback;
  return Number(value);
}

function optionalInt(value: string): number | null {
  if (!value.trim()) return null;
  return Number(value);
}

export function parseMisconceptions(value: string): { wrong_move: string; broken_kc: string }[] {
  return lines(value).map((line) => {
    const [wrong, broken = ""] = line.split("->");
    return { wrong_move: (wrong ?? "").trim(), broken_kc: broken.trim() };
  });
}

export function testerPayload(
  values: TesterValues,
  typeFields: Record<string, unknown> = {},
): PromptTesterRequest {
  return {
    course_title: values["Course title"] ?? "",
    course_description: values["Course description"] ?? "",
    audience: values.Audience || "9-11",
    kind: values.Kind || "mastery",
    minutes: optionalInt(values.Minutes ?? ""),
    component_title: values["Component title"] ?? "",
    component_code: values["Component code"] ?? "",
    component_description: values["Component description"] ?? "",
    kc_type: values.Type ?? "",
    core_truth: values["Core truth"] ?? "",
    rubric: lines(values["Rubric lines"] ?? ""),
    misconceptions: parseMisconceptions(values.Misconceptions ?? ""),
    prerequisite_codes: pieces(values["Prerequisite codes"] ?? ""),
    encompasses_codes: pieces(values["Encompass codes"] ?? ""),
    transfer_case: values["Transfer case"] ?? "",
    counterfactual: values.Counterfactual ?? "",
    type_fields: typeFields,
    move_index: whole(values["Move index"] ?? "", 1),
    choice_on_screen: values["Choice widget"] === "yes" ? "yes" : "no",
    prerequisite_status: values["Prerequisite status"] ?? "",
    course_position: values["Course position"] ?? "",
    display_name: values["Display name"] ?? "",
    age: optionalInt(values.Age ?? ""),
    reading_level: values["Reading level"] ?? "",
    modality: values.Modality ?? "",
    interests: pieces(values.Interests ?? ""),
    attempts: whole(values["Attempts on this move"] ?? "", 0),
    hint_tier: values["Hint tier already given"] || "nudge",
    component_status: values["Component status"] || "unknown",
    stability: values.Stability ?? "0",
    last_answer: values["Last answer"] ?? "",
    last_misconception: values["Last misconception"] ?? "",
    minutes_used: whole(values["Minutes used"] ?? "", 0),
    support_band: values["Support band"] || "ready",
    persona: values.Persona,
    lexicon: values.Lexicon,
    metaphors: values.Metaphors,
    sidekick: values.Sidekick,
    use_interests: values["Use interests"] === "no" ? "no" : "yes",
    instructive: whole(values.Instructive ?? "", 3),
    struggle_window: values["Struggle window"] || "standard",
    stay_on_course: values["Stay on course"] === "no" ? "no" : "yes",
    anti_spoiler: values["Anti-spoiler"] === "no" ? "no" : "yes",
    one_question: values["One question"] === "no" ? "no" : "yes",
    misconception_policy: values["Misconception policy"] || "retry_once",
    enrichment: values.Enrichment || "on_request",
    growth_praise: values["Growth-mindset praise"] === "no" ? "no" : "yes",
    self_explanation: values["Self-explanation"] === "no" ? "no" : "yes",
    reveals: whole(values["Reveals used"] ?? "", 0),
    off_course_count: whole(values["Off-course count"] ?? "", 0),
    rubric_met: pieces(values["Rubric points met"] ?? ""),
    last_messages: values["Last four messages"] ?? "",
    affect: values.Affect ?? "",
    help_requested: values["Help requested"] === "yes" ? "yes" : "no",
    last_practiced: values["Last practiced"] ?? "",
    redirect_pending: values["Redirect pending"] === "yes" ? "yes" : "no",
    enrichment_turns: whole(values["Enrichment turns"] ?? "", 0),
    unit_close: values["Unit close"] === "yes" ? "yes" : "no",
    course_outro: values["Course outro"] === "yes" ? "yes" : "no",
  };
}

export function applyResult(values: TesterValues, result: PromptTesterResult): TesterValues {
  return {
    ...values,
    "Move name": result.move_name,
    Evidence: result.evidence,
    "Effective struggle window": result.effective_struggle_window,
    "Effective enrichment": result.effective_enrichment,
    "Asks why": result.asks_why,
  };
}
