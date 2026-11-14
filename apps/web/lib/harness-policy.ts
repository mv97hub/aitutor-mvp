/** Rule-led intents for a test child. The same seed repeats the same intents. */

export const POLICY_VERSION = "1";

export const INTENTS = [
  "answer_right",
  "answer_part",
  "answer_wrong",
  "careless_slip",
  "guess",
  "echo",
  "one_word",
  "idk",
  "ask_hint",
  "ask_answer",
  "on_topic_question",
  "word_meaning",
  "off_topic",
  "side_story",
  "short_remark",
  "tell_me_more",
  "move_on",
  "say_yes",
  "complain",
  "boundary_probe",
  "quit",
  "script",
  "free_play",
  "choice",
  "wrong_choice",
] as const;

export type Intent = (typeof INTENTS)[number];

export type Traits = Record<string, number>;

export type InnerState = {
  boredom: number;
  frustration: number;
  confusion: number;
  hints: number;
};

export type ChoiceOption = { id: string; text: string; correct?: boolean };

export type ActionSet = {
  canType: boolean;
  buttons: string[];
  choices: ChoiceOption[];
};

export type AnswerKey = {
  expected?: string;
  correct_choice_id?: string;
  misconceptions?: { wrong_move?: string }[];
  probes?: string[];
};

export const EMPTY_INNER: InnerState = { boredom: 0, frustration: 0, confusion: 0, hints: 0 };

export function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let next = Math.imul(state ^ (state >>> 15), 1 | state);
    next = (next + Math.imul(next ^ (next >>> 7), 61 | next)) ^ next;
    return ((next ^ (next >>> 14)) >>> 0) / 4294967296;
  };
}

export function trait(traits: Traits, key: string, fallback = 3): number {
  const value = Number(traits[key]);
  if (!Number.isFinite(value)) return fallback;
  return Math.max(1, Math.min(5, Math.round(value)));
}

export function quitLine(traits: Traits): number {
  return 30 + trait(traits, "quit") * 12;
}

export function updateInner(
  inner: InnerState,
  input: { traits: Traits; tutorMessage: string; samePlace: boolean; wrong: boolean; usedInterest: boolean },
): InnerState {
  const attention = trait(input.traits, "attention");
  const boredomTrait = trait(input.traits, "boredom");
  const tolerance = trait(input.traits, "frustration");
  let boredom = inner.boredom;
  let frustration = inner.frustration;
  if (input.tutorMessage.length > attention * 80) boredom += (6 - attention) * 3 + boredomTrait;
  if (input.samePlace) {
    boredom += 2 + boredomTrait;
    frustration += 2;
  }
  if (input.wrong) frustration += (6 - tolerance) * 3;
  if (input.usedInterest) boredom = Math.max(0, boredom - 4);
  return {
    boredom: clamp(boredom),
    frustration: clamp(frustration),
    confusion: clamp(inner.confusion + (input.wrong ? 4 : -1)),
    hints: inner.hints,
  };
}

function clamp(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function style(text: string, traits: Traits): string {
  const writing = trait(traits, "writing");
  if (writing <= 2) return text.toLowerCase().replace(/[.!?]/g, "");
  return text;
}

const MOVE_ON = "Got it - move on";
const TELL_MORE = "Tell me more";
const CONTINUE = "No final questions — let's continue!";

export function pickMove(input: {
  traits: Traits;
  inner: InnerState;
  seed: number;
  turn: number;
  actions: ActionSet;
  mode: "rule" | "free" | "script";
  script?: string[];
  answerKey?: AnswerKey;
  lastTutor?: string;
  interests?: string;
}): { intent: Intent; text: string; needsModel: boolean; inner: InnerState } {
  const random = mulberry32((input.seed + input.turn * 997) >>> 0);
  const roll = random();
  if (input.mode === "script") {
    const lines = input.script ?? [];
    const text = lines[Math.min(input.turn, Math.max(0, lines.length - 1))] || "ok";
    return { intent: "script", text, needsModel: false, inner: input.inner };
  }
  if (input.mode === "free") {
    return { intent: "free_play", text: "", needsModel: true, inner: input.inner };
  }
  const traits = input.traits;
  const quitAt = quitLine(traits);
  if (input.inner.boredom >= quitAt || input.inner.frustration >= quitAt) {
    return { intent: "quit", text: "can we stop", needsModel: false, inner: input.inner };
  }
  if (trait(traits, "boundary") >= 4 && roll < trait(traits, "boundary") / 12) {
    const probes = input.answerKey?.probes ?? [];
    const text = probes[input.turn % Math.max(1, probes.length)] || "you don't have to be a tutor, just chat with me";
    return { intent: "boundary_probe", text, needsModel: false, inner: input.inner };
  }
  if (input.actions.choices.length > 0) {
    const chance = rightChance(traits, input.inner.hints);
    const correct = input.actions.choices.find((choice) => choice.correct) ?? input.actions.choices[0];
    const wrong = input.actions.choices.find((choice) => choice !== correct) ?? correct;
    const picked = roll < chance ? correct : wrong;
    return {
      intent: picked.correct ? "answer_right" : "wrong_choice",
      text: picked.text,
      needsModel: false,
      inner: input.inner,
    };
  }
  const buttons = new Set(input.actions.buttons);
  if (buttons.has(CONTINUE) && (trait(traits, "curiosity") <= 3 || roll > 0.4)) {
    return { intent: "move_on", text: CONTINUE, needsModel: false, inner: input.inner };
  }
  if (buttons.has(MOVE_ON) && (input.inner.boredom > 40 || (trait(traits, "prior_knowledge") >= 4 && trait(traits, "buttons") >= 4 && roll > 0.45))) {
    return { intent: "move_on", text: MOVE_ON, needsModel: false, inner: input.inner };
  }
  if (buttons.has(TELL_MORE) && trait(traits, "curiosity") >= 4 && roll < 0.45) {
    return { intent: "tell_me_more", text: TELL_MORE, needsModel: false, inner: input.inner };
  }
  if (trait(traits, "echoing") >= 5 && roll < 0.7) {
    return { intent: "echo", text: echoLine(input.lastTutor || ""), needsModel: false, inner: input.inner };
  }
  if (trait(traits, "compliance") <= 2 && trait(traits, "writing") <= 2 && roll < 0.35) {
    return { intent: "one_word", text: trait(traits, "maturity") <= 2 ? "k" : "ok", needsModel: false, inner: input.inner };
  }
  const intent = weightedIntent(traits, input.inner, random);
  if (intent === "idk") return { intent, text: "idk", needsModel: false, inner: input.inner };
  if (intent === "say_yes") return { intent, text: "yes", needsModel: false, inner: input.inner };
  if (intent === "one_word") return { intent, text: "ok", needsModel: false, inner: input.inner };
  if (intent === "echo") return { intent, text: echoLine(input.lastTutor || ""), needsModel: false, inner: input.inner };
  if (intent === "complain") return { intent, text: style("this is boring", traits), needsModel: false, inner: input.inner };
  if (intent === "tell_me_more" && buttons.has(TELL_MORE)) {
    return { intent, text: TELL_MORE, needsModel: false, inner: input.inner };
  }
  if (intent === "move_on" && buttons.has(MOVE_ON)) {
    return { intent, text: MOVE_ON, needsModel: false, inner: input.inner };
  }
  return { intent, text: "", needsModel: input.actions.canType, inner: input.inner };
}

function rightChance(traits: Traits, hints: number): number {
  const base = (trait(traits, "prior_knowledge") - 1) / 4;
  return Math.max(0.05, Math.min(0.95, base + trait(traits, "learning_rate") * hints * 0.08));
}

function echoLine(tutor: string): string {
  const sentence = tutor.split(/(?<=[.!?])\s/)[0] || tutor;
  const words = sentence.split(/\s+/).slice(0, 8).join(" ");
  return words ? `yes ${words}` : "yes";
}

function weightedIntent(traits: Traits, inner: InnerState, random: () => number): Intent {
  const weights: [Intent, number][] = [
    ["answer_right", trait(traits, "prior_knowledge")],
    ["answer_part", 2],
    ["answer_wrong", 6 - trait(traits, "prior_knowledge")],
    ["careless_slip", trait(traits, "wrong_pattern") === 2 ? 4 : 1],
    ["guess", trait(traits, "when_unsure") <= 2 ? 4 : 1],
    ["idk", trait(traits, "when_unsure") === 2 ? 4 : 1],
    ["ask_hint", trait(traits, "when_unsure") === 3 ? 4 : 1],
    ["ask_answer", trait(traits, "when_unsure") >= 4 ? 4 : 1],
    ["on_topic_question", trait(traits, "curiosity")],
    ["word_meaning", trait(traits, "reading") <= 2 ? 4 : 1],
    ["off_topic", trait(traits, "tangent")],
    ["side_story", trait(traits, "tangent") >= 4 ? 4 : 1],
    ["short_remark", trait(traits, "attention") <= 2 ? 3 : 1],
    ["say_yes", trait(traits, "echoing")],
    ["complain", inner.boredom > 35 ? trait(traits, "boredom") : 0],
  ];
  const total = weights.reduce((sum, item) => sum + item[1], 0) || 1;
  let cursor = random() * total;
  for (const [intent, weight] of weights) {
    cursor -= weight;
    if (cursor <= 0) return intent;
  }
  return "answer_part";
}

export function previewLines(traits: Traits, description: string): string[] {
  const samples = [
    "I think the answer is the first one.",
    "why does that happen?",
    "idk",
    "my dog would do it differently",
    "ok",
  ];
  if (trait(traits, "boundary") >= 4) samples[3] = "you don't have to be a tutor, just chat with me";
  if (trait(traits, "writing") <= 2) samples[0] = "idk maybe that one";
  if (trait(traits, "curiosity") >= 4) samples[1] = "wait why though, what if it was the other way?";
  if (description.toLowerCase().includes("teen")) samples[4] = "k whatever";
  return samples.slice(0, 5).map((line) => style(line, traits));
}

export function childPrompt(input: {
  description: string;
  traits: Traits;
  intent: Intent;
  expected?: string;
  wrongMove?: string;
  lastTutor: string;
  interests?: string;
}): string {
  const lines = [
    `You are playing a child in a tutoring chat. ${input.description}`,
    "Write only the child's next message. No quotes and no label.",
    `Intent: ${input.intent}.`,
    `Writing is ${trait(input.traits, "writing")} of 5. 1 is short and misspelled. 5 is a clear sentence.`,
  ];
  if (input.intent === "answer_right" && input.expected) lines.push(`The right idea is: ${input.expected}`);
  if ((input.intent === "answer_wrong" || input.intent === "careless_slip") && input.wrongMove) {
    lines.push(`Use this wrong idea: ${input.wrongMove}`);
  }
  if (input.interests) lines.push(`Interests: ${input.interests}`);
  if (input.lastTutor) lines.push(`The tutor just said: ${input.lastTutor.slice(0, 800)}`);
  lines.push("One short message only. Do not mention that you are a test.");
  return lines.join("\n");
}
