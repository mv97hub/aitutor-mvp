/** Form state for the KC Prompt Tester. The API calls build_kc_prompt. */

import {
  CHALLENGE_APPETITE_OPTIONS,
  COMMUNICATION_TONE_OPTIONS,
  EXPLANATION_STYLE_OPTIONS,
  EXPRESSION_STYLE_OPTIONS,
  GRADE_BAND_OPTIONS,
  HUMOR_AND_WIT_OPTIONS,
  INTEREST_TAG_OPTIONS,
  INTEREST_WEAVING_OPTIONS,
  LAYER_FIELDS,
  LAYER_HEADINGS,
  LEARNING_SUPPORT_OPTIONS,
  METAPHOR_OPTIONS,
  PERSONA_OPTIONS,
  READING_LEVEL_OPTIONS,
  RESPONSE_LENGTH_OPTIONS,
  SIDEKICK_OPTIONS,
  VOCABULARY_REGISTER_OPTIONS,
  gradeBandForAge,
  normalizeExplanationStyleOption,
  type LayerField,
} from "./kc-layer-fields.ts";
import { BLOCK_LABELS, BLOCK_TYPES, isBlockType } from "./kc-blocks.ts";
import { AUDIENCES, KINDS, type KcBlock, type KcBlockType, type KcComponent, type KcCourse } from "./kc.ts";
import {
  DEFAULT_KC_TUTOR_CONFIG,
  OVERARCHING_FIELDS,
  kcTutorConfigFrom,
  type KcTutorConfig,
} from "./kc-tutor-config.ts";
import type { Student, TutorProfile } from "./types.ts";

export { LAYER_HEADINGS, INTEREST_TAG_OPTIONS };

export const READ_ONLY_DERIVED = [
  "Move name",
  "Evidence",
] as const;

export const DEFAULT_TUTOR_PROFILE: TutorProfile = {
  instructive: 3,
  persona: "coach",
  lexicon: "adaptive_to_child",
  vocabulary_register: "adaptive_to_child",
  interest_weaving: "subtle_natural",
  humor_and_wit: "light_warm",
  voice_override: false,
  metaphors: "everyday",
  sidekick: "none",
  struggle_window: "standard",
  anti_spoiler: true,
  one_question: true,
  use_interests: true,
  stay_on_course: true,
  growth_praise: true,
  misconception_policy: "explain_and_retry_once",
  self_explanation: true,
  enrichment: "on_request",
  kc_tutor_config: DEFAULT_KC_TUTOR_CONFIG,
};

const YES_NO = new Set([
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
  "Topic index",
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

function overarchingOptions(key: string): readonly (readonly [string, string])[] {
  const field = OVERARCHING_FIELDS.find((item) => item.key === key);
  return field && field.kind === "enum" ? field.options : [];
}

export const FIELD_OPTIONS: Record<string, readonly (readonly [string, string])[]> = {
  Audience: AUDIENCES.map((band) => [band, band] as const),
  Kind: KINDS.map((kind) => [kind.id, kind.label] as const),
  Type: [["", "Unset"], ...BLOCK_TYPES.map((type) => [type, BLOCK_LABELS[type]] as const)],
  Substep: [
    ["", "Default"],
    ["main", "Main"],
    ["choice", "Choose option"],
    ["awaiting_why", "Explain why"],
    ["predict", "Predict"],
    ["contrast_and_rule", "Contrast and rule"],
    ["transfer", "Transfer"],
    ["initial_thesis", "Initial position"],
    ["counterexample_probe", "Counterexample probe"],
    ["hook_and_predict", "Wonder and predict"],
    ["faded_step", "Faded step"],
    ["solo_solve", "Solo problem"],
    ["critique", "Identify and fix"],
    ["initial_explanation", "Peer explanation"],
    ["peer_follow_up", "Peer follow-up"],
    ["recall", "Cued recall"],
    ["elaborate_why", "Elaborative why"],
    ["explain_topic", "Explain topic"],
    ["summary_check", "Summary and final questions"],
  ],
  Persona: PERSONA_OPTIONS,
  "Vocabulary register": VOCABULARY_REGISTER_OPTIONS,
  "Interest weaving": INTEREST_WEAVING_OPTIONS,
  Metaphors: METAPHOR_OPTIONS,
  "Humor and wit": HUMOR_AND_WIT_OPTIONS,
  Sidekick: SIDEKICK_OPTIONS,
  "Orient framing": overarchingOptions("orient_framing"),
  "Instructional stance": overarchingOptions("instructional_stance"),
  "Scaffolding escalation": overarchingOptions("scaffolding_escalation"),
  "Stay on course": overarchingOptions("stay_on_course"),
  "Misconception policy": overarchingOptions("misconception_policy"),
  "Prerequisite support policy": overarchingOptions("prerequisite_support_policy"),
  "Encouragement style": overarchingOptions("encouragement_style"),
  "Close summary depth": overarchingOptions("close_summary_depth"),
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
  "Grade band": [["", "Auto from age"], ...GRADE_BAND_OPTIONS],
  "Reading level": [["", "Unset"], ...READING_LEVEL_OPTIONS],
  "Response length": RESPONSE_LENGTH_OPTIONS,
  "Expression style": EXPRESSION_STYLE_OPTIONS,
  "Explanation style": EXPLANATION_STYLE_OPTIONS,
  "Challenge appetite": CHALLENGE_APPETITE_OPTIONS,
  "Communication tone": COMMUNICATION_TONE_OPTIONS,
  "Learning support": LEARNING_SUPPORT_OPTIONS,
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
  blocks: KcBlock[];
  move_index: number;
  active_substep: string;
  topic_index: number;
  choice_on_screen: string;
  prerequisite_status: string;
  course_position: string;
  display_name: string;
  age: number | null;
  grade_band: string;
  reading_level: string;
  response_length: string;
  expression_style: string;
  explanation_style: string;
  challenge_appetite: string;
  communication_tone: string;
  learning_support: string;
  interest_tags: string[];
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
  vocabulary_register: string;
  interest_weaving: string;
  metaphors: string;
  humor_and_wit: string;
  sidekick: string;
  use_interests: string;
  orient_framing: string;
  instructional_stance: string;
  scaffolding_escalation: string;
  stay_on_course: string;
  misconception_policy: string;
  prerequisite_support_policy: string;
  encouragement_style: string;
  close_summary_depth: string;
  kc_tutor_config: KcTutorConfig;
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
  active_block_type?: string;
  active_block_type_label?: string;
  active_substep?: string;
  active_substep_label?: string;
  max_retries?: number;
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

export function emptyTesterValues(profile: TutorProfile = DEFAULT_TUTOR_PROFILE): TesterValues {
  const values: TesterValues = {};
  for (const field of formFields()) values[field.name] = "";
  const cfg = kcTutorConfigFrom(profile.kc_tutor_config);
  const vocab = profile.vocabulary_register || profile.lexicon || "adaptive_to_child";
  const weaving =
    profile.interest_weaving || (profile.use_interests === false ? "off" : "subtle_natural");
  const humor = profile.humor_and_wit || "light_warm";
  return {
    ...values,
    Audience: "9-11",
    Kind: "mastery",
    "Move index": "1",
    "Choice widget": "no",
    "Grade band": "upper_elementary",
    "Response length": "balanced",
    "Expression style": "short_phrases",
    "Explanation style": "concrete_examples",
    "Challenge appetite": "steady",
    "Communication tone": "warm_and_encouraging",
    "Learning support": "none",
    "Interest tags": "",
    "Attempts on this move": "0",
    "Hint tier already given": "nudge",
    "Component status": "unknown",
    Stability: "0",
    "Minutes used": "0",
    "Support band": "ready",
    Persona: profile.persona || "coach",
    "Vocabulary register": vocab,
    "Interest weaving": weaving,
    Metaphors: profile.metaphors || "everyday",
    "Humor and wit": humor,
    Sidekick: profile.sidekick || "none",
    "Orient framing": cfg.overarching.orient_framing || "elaborate_outline",
    "Instructional stance": cfg.overarching.instructional_stance || "guided_discovery",
    "Scaffolding escalation":
      cfg.overarching.scaffolding_escalation || "progressive_nudge_then_scaffold",
    "Stay on course": cfg.overarching.stay_on_course || "brief_answer_then_return",
    "Misconception policy": cfg.overarching.misconception_policy || "explain_and_retry_once",
    "Prerequisite support policy":
      cfg.overarching.prerequisite_support_policy || "inline_micro_recap",
    "Encouragement style": cfg.overarching.encouragement_style || "process_praise",
    "Close summary depth": cfg.overarching.close_summary_depth || "diagnostic_strengths_and_gaps",
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
  const cp = child.child_profile;
  const interestsList = child.interests ?? [];
  const favText = cp?.interests ?? interestsList.join(", ");
  return {
    ...values,
    "Display name": child.display_name ?? "",
    Age: child.age == null ? "" : String(child.age),
    "Grade band": child.grade_band ?? cp?.grade_band ?? (child.age == null ? "" : gradeBandForAge(child.age)),
    "Reading level": child.reading_level || cp?.reading_level || "",
    "Response length": child.response_length ?? cp?.response_length ?? "balanced",
    "Expression style": child.expression_style ?? cp?.expression_style ?? "short_phrases",
    "Explanation style":
      child.explanation_style ??
      cp?.explanation_style ??
      (child.modality ? normalizeExplanationStyleOption(child.modality) : "concrete_examples"),
    Modality: child.modality ?? "",
    "Challenge appetite": child.challenge_appetite ?? cp?.challenge_appetite ?? "steady",
    "Communication tone": child.communication_tone ?? cp?.communication_tone ?? "warm_and_encouraging",
    "Learning support": child.learning_support ?? cp?.learning_support ?? "none",
    "Interest tags": (child.interest_tags ?? cp?.interest_tags ?? []).join(", "),
    Interests: favText,
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

/** Blocks the prompt tester previews. Only catalog block types are kept. */
export function blocksForUnit(unit: KcComponent): KcBlock[] {
  return (unit.blocks ?? [])
    .filter((block): block is KcBlock => isBlockType(block.type))
    .map((block) => ({
      id: block.id,
      type: block.type,
      data: structuredClone(block.data),
    }));
}

export function activeBlockTypeFor(values: TesterValues, blocks: KcBlock[] = []): KcBlockType {
  const moveIndex = Number(values["Move index"] || "1");
  const idx = blocks.length
    ? Math.min(Math.max(Number.isFinite(moveIndex) ? moveIndex : 1, 1), blocks.length) - 1
    : 0;
  const fromBlocks = blocks[idx]?.type;
  if (fromBlocks && isBlockType(fromBlocks)) return fromBlocks;
  const fromTypeField = values.Type ?? "";
  if (isBlockType(fromTypeField)) return fromTypeField;
  return "topic_goal";
}

export function testerPayload(
  values: TesterValues,
  typeFields: Record<string, unknown> = {},
  blocks: KcBlock[] = [],
  tutorConfig?: KcTutorConfig,
): PromptTesterRequest {
  const baseCfg = kcTutorConfigFrom(tutorConfig);
  const orient_framing = values["Orient framing"] || baseCfg.overarching.orient_framing || "elaborate_outline";
  const instructional_stance =
    values["Instructional stance"] || baseCfg.overarching.instructional_stance || "guided_discovery";
  const scaffolding_escalation =
    values["Scaffolding escalation"] ||
    baseCfg.overarching.scaffolding_escalation ||
    "progressive_nudge_then_scaffold";
  const stay_on_course =
    values["Stay on course"] || baseCfg.overarching.stay_on_course || "brief_answer_then_return";
  const misconception_policy =
    values["Misconception policy"] || baseCfg.overarching.misconception_policy || "explain_and_retry_once";
  const prerequisite_support_policy =
    values["Prerequisite support policy"] ||
    baseCfg.overarching.prerequisite_support_policy ||
    "inline_micro_recap";
  const encouragement_style =
    values["Encouragement style"] || baseCfg.overarching.encouragement_style || "process_praise";
  const close_summary_depth =
    values["Close summary depth"] ||
    baseCfg.overarching.close_summary_depth ||
    "diagnostic_strengths_and_gaps";

  const vocabulary_register = values["Vocabulary register"] || values.Lexicon || "adaptive_to_child";
  const interest_weaving =
    values["Interest weaving"] || (values["Use interests"] === "no" ? "off" : "subtle_natural");
  const humor_and_wit = values["Humor and wit"] || "light_warm";
  const persona = values.Persona || "coach";
  const metaphors = values.Metaphors || "everyday";
  const sidekick = values.Sidekick || "none";

  const kc_tutor_config: KcTutorConfig = {
    overarching: {
      orient_framing,
      instructional_stance,
      scaffolding_escalation,
      stay_on_course,
      misconception_policy,
      prerequisite_support_policy,
      encouragement_style,
      close_summary_depth,
    },
    blocks: baseCfg.blocks,
  };

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
    blocks,
    move_index: whole(values["Move index"] ?? "", 1),
    active_substep: values.Substep ?? "",
    topic_index: whole(values["Topic index"] ?? "", 0),
    choice_on_screen: values["Choice widget"] === "yes" ? "yes" : "no",
    prerequisite_status: values["Prerequisite status"] ?? "",
    course_position: values["Course position"] ?? "",
    display_name: values["Display name"] ?? "",
    age: optionalInt(values.Age ?? ""),
    grade_band: values["Grade band"] ?? "",
    reading_level: values["Reading level"] ?? "",
    response_length: values["Response length"] ?? "",
    expression_style: values["Expression style"] ?? "",
    explanation_style: values["Explanation style"] ?? "",
    challenge_appetite: values["Challenge appetite"] ?? "",
    communication_tone: values["Communication tone"] ?? "",
    learning_support: values["Learning support"] ?? "",
    interest_tags: pieces(values["Interest tags"] ?? "").slice(0, 4),
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
    persona,
    lexicon: vocabulary_register,
    vocabulary_register,
    interest_weaving,
    metaphors,
    humor_and_wit,
    sidekick,
    use_interests: interest_weaving === "off" ? "no" : "yes",
    orient_framing,
    instructional_stance,
    scaffolding_escalation,
    stay_on_course,
    misconception_policy,
    prerequisite_support_policy,
    encouragement_style,
    close_summary_depth,
    kc_tutor_config,
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
  };
}
