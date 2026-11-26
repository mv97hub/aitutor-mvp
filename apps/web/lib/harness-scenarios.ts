/** Authored learner turns for bounded regression cases. Match only what the learner can see. */
export type ScenarioInput = {
  personaNumber: number;
  blockType: string;
  substep: string;
  tutor: string;
  question?: string;
  canType: boolean;
  buttons: string[];
  choices: { id: string; text: string }[];
  history: { role: string; content: string; step?: number }[];
  blockIndex?: number;
  lastScenarioLine?: string;
};

type Variant = { id: string; label: string };
type ScenarioGroup = {
  id: string;
  label: string;
  personas: number[];
  blockTypes: string[];
  fixture: string;
  context: string;
  variants: Variant[];
  respond: (id: string, input: ScenarioInput) => string | undefined;
};

const FORMULA = "The change in CPI divided by the old CPI, times 100.";
const DISCLOSED = "The inflation rate is the change in CPI divided by the old CPI, times 100.";
const PARAPHRASE = "Take the increase, divide by the starting index and multiply by a hundred.";
const STRUGGLE = "I still don't know which number goes underneath.";
const WRONG_RATE = "Inflation is 12% because the index went up 12 points.";
const CORRECT_RATE = "It rose by 10% because 12 divided by 120 is 0.1.";
const WRONG_REASON = "I guessed. The index went up ten points.";
const SOUND_REASON = "The index rose 12 points. Dividing by the starting 120 gives 10%.";
const CPI_FORMULA_TYPES = ["topic_goal", "retrieval_check", "worked_example"];
const CPI_NUMBER_TYPES = ["worked_example", "case_study", "mcq"];

function prompt(input: ScenarioInput) {
  return [input.tutor, input.question].filter(Boolean).join("\n");
}

function asksFormula(input: ScenarioInput) {
  const visible = prompt(input);
  return ["main", "recall", "faded_step", "solo_solve"].includes(input.substep)
    && /\bCPI\b|consumer price index/i.test(visible) && /inflation/i.test(visible)
    && /(?:what|which|give|write|state|tell|explain)[^?!.]{0,65}\bformula\b|how (?:do|would|can) (?:you|we) (?:calculate|work out) (?:the )?(?:rate of )?inflation/i.test(visible);
}

function asksRate(input: ScenarioInput) {
  const visible = prompt(input);
  return /\bCPI\b|consumer price index/i.test(visible)
    && /\b(?:from )?120\s*(?:to|→)\s*132\b/i.test(visible)
    && /(?:what|calculate|work out|find|which|how (?:much|large))[^?!.]{0,100}(?:inflation|percent(?:age)?|rate)/i.test(visible);
}

function onBlock(input: ScenarioInput) {
  return input.history.filter(message => input.blockIndex === undefined || message.step === input.blockIndex);
}

function tutorLines(input: ScenarioInput) {
  return [...onBlock(input).filter(message => message.role === "assistant").map(message => message.content), input.tutor];
}

function alreadySaid(input: ScenarioInput, line: string, allBlocks = false) {
  return (allBlocks ? input.history : onBlock(input)).some(message =>
    (message.role === "user" || message.role === "child") && message.content.split("\n")[0].trim() === line);
}

function typedOnce(input: ScenarioInput, line: string) {
  return input.canType && !input.choices.length && !alreadySaid(input, line) ? line : undefined;
}

function echo(id: string, input: ScenarioInput) {
  const reply = id === "disclosure-verbatim" ? DISCLOSED : id === "disclosure-paraphrase" ? PARAPHRASE : STRUGGLE;
  if (asksFormula(input) && tutorLines(input).some(line => line.includes(DISCLOSED))) return typedOnce(input, reply);
  if (input.blockType === "worked_example" && input.substep === "solo_solve" && asksRate(input)
    && alreadySaid(input, reply, true)
    && !tutorLines(input).some(line => /\b(?:10\s*%|10\s+percent|ten\s+percent)/i.test(line))
    && !input.history.some(m => m.step !== undefined && m.step !== input.blockIndex && m.role === "assistant"
      && asksRate({...input, tutor: m.content, question: undefined}))) {
    return typedOnce(input, id === "disclosure-struggle" ? "I still need a hint on this new one." : CORRECT_RATE);
  }
}

function misconception(id: string, input: ScenarioInput) {
  if (input.blockType === "retrieval_check" && input.substep === "recall"
    && /\bwho (?:wrote|is the author of)\s+["“']?Romeo and Juliet\b/i.test(prompt(input))
    && alreadySaid(input, WRONG_RATE, true)) return typedOnce(input, "William Shakespeare.");
  if (input.blockType !== "worked_example" || !["faded_step", "solo_solve"].includes(input.substep)) return;
  if (!alreadySaid(input, WRONG_RATE)) return asksRate(input) ? typedOnce(input, WRONG_RATE) : undefined;
  const correction = input.tutor;
  const worked = /12\s*(?:\/|÷|divided by)\s*120/i.test(correction) && /10\s*(?:%|percent)/i.test(correction);
  if (worked) return typedOnce(input, id === "cpi-belief-revises" ? CORRECT_RATE : "I still think 12 points means 12%.");
}

function closing(id: string, input: ScenarioInput) {
  if (input.substep !== "summary_check") return;
  if (id === "closing-continue") {
    const button = input.buttons.find(text => /no final questions.*continue/i.test(text));
    if (button && !alreadySaid(input, button)) return button;
  }
  if (id === "closing-acknowledges") return typedOnce(input, "ok");
  if (id === "closing-more") return typedOnce(input, "Ask me one more question.");
  if (id === "closing-stops" && input.canType && !input.choices.length) {
    const history = onBlock(input);
    const invitation = /(?:last|final) questions?|questions? (?:for me )?before (?:we|you)|before we (?:finish|wrap|close)/i;
    const start = history.findIndex(m => m.role === "assistant" && invitation.test(m.content));
    if (start < 0 && !invitation.test(input.tutor)) return;
    const replies = start < 0 ? [] : history.slice(start + 1).filter(m => ["child", "user"].includes(m.role) && m.content === "k");
    if (replies.length < 2) return "k";
    return typedOnce(input, "Can we stop now?");
  }
}

function clarify(id: string, input: ScenarioInput) {
  if (input.blockType === "mcq" && input.substep === "choice" && asksRate(input)
    && (id === "reason-guess" || id === "reason-sound")) {
    const choice = input.choices.find(option => /^10\s*(?:%|percent)\.?$/i.test(option.text.trim()));
    if (choice && !alreadySaid(input, choice.text) && !alreadySaid(input, choice.id)) return choice.text;
  }
  if (input.blockType === "mcq" && input.substep === "awaiting_why"
    && (id === "reason-guess" || id === "reason-sound")
    && (/^10\s*(?:%|percent)\.?$/i.test(input.lastScenarioLine || "") || input.lastScenarioLine === WRONG_REASON
      || onBlock(input).some(m => m.role === "assistant" && asksRate({...input, tutor: m.content, question: undefined})))
    && onBlock(input).some(m => ["user", "child"].includes(m.role) && /^10\s*(?:%|percent)\.?$/i.test(m.content.split("\n")[0].trim()))) {
    if (id === "reason-guess" && !alreadySaid(input, WRONG_REASON)) return typedOnce(input, WRONG_REASON);
    return typedOnce(input, SOUND_REASON);
  }
  if (input.blockType !== "mcq" && ["solo_solve", "transfer"].includes(input.substep) && asksRate(input)) {
    if (id === "reason-clarify") return typedOnce(input, "What does CPI mean?");
    if (id === "reason-partial") return typedOnce(input, "It went up 12 points. Which number do I divide by?");
  }
}

export const SCENARIO_GROUPS: ScenarioGroup[] = [
  {
    id: "formula", label: "Confidence and the inflation formula", personas: [5],
    blockTypes: CPI_FORMULA_TYPES, fixture: "Inflation formula, practice and a new topic", context: "A typed recall, main question or worked step must ask for the CPI inflation formula. Compare credit for the two complete answers and coaching for the missing denominator.",
    variants: [
      {id: "cpi-formula-hesitant", label: "Complete, tentative"}, {id: "cpi-formula-statement", label: "Complete, declarative"},
      {id: "cpi-formula-incomplete", label: "Confident, missing the denominator"},
    ],
    respond(id, input) {
      if (!asksFormula(input)) return;
      const line = id === "cpi-formula-hesitant" ? "Is it the change in CPI divided by the old CPI, times 100?"
        : id === "cpi-formula-statement" ? FORMULA : "It's the new CPI minus the old CPI.";
      return typedOnce(input, line);
    },
  }, {
    id: "expression", label: "Expression and attachment inference", personas: [9, 10], blockTypes: ["case_study", "socratic"], fixture: "Interpret a character’s feelings",
    context: "Ask whether avoidant attachment means the child does not care. Compare the inference across wording, then inspect the fluent overclaim.",
    variants: [{id: "attachment-short", label: "Short and misspelled"}, {id: "attachment-fluent", label: "Fluent equivalent"}, {id: "attachment-wrong", label: "Fluent, unsupported inference"}],
    respond(id, input) {
      if (!["predict", "contrast_and_rule", "transfer", "initial_thesis", "counterexample_probe"].includes(input.substep)
        || !/avoidan[tc]/i.test(prompt(input)) || !/care|love|feelings/i.test(prompt(input))) return;
      const line = id === "attachment-short" ? "Avoidant, but it dont prove he dont care."
        : id === "attachment-fluent" ? "It suggests avoidant attachment, but it does not prove the child does not care."
        : "Avoidant attachment proves the child does not care about their caregiver.";
      return typedOnce(input, line);
    },
  }, {
    id: "reader", label: "Reading support", personas: [2, 8], blockTypes: ["passage_ela"], fixture: "Short informational passage · River roads, or Difficulty stress case · Hamlet",
    context: "Both variants ask to reread River roads in the same words. The simulated learner’s response-length setting changes for this run only. The separate difficulty test uses the displayed Hamlet passage.",
    variants: [{id: "reread-short", label: "Reread · bite-sized setting"}, {id: "reread-detail", label: "Reread · detailed setting"}, {id: "reread-stress", label: "Difficulty stress case · Hamlet"}],
    respond(id, input) {
      if (input.substep !== "central_idea" || !/central idea|main idea|mostly about/i.test(prompt(input))) return;
      if (id === "reread-stress" && !tutorLines(input).some(line => /to be,? or not to be/i.test(line))) return;
      return typedOnce(input, "Can I read the whole passage again and get an explanation?");
    },
  }, {
    id: "disclosure", label: "Recall after disclosure and fresh transfer", personas: [11], blockTypes: CPI_FORMULA_TYPES, fixture: "Inflation formula, practice and a new topic",
    context: `The tutor must have said “${DISCLOSED}” in the active block and ask for the formula. Follow it with a fresh solo CPI problem going from 120 to 132. Check assisted recall and transfer separately.`,
    variants: [{id: "disclosure-verbatim", label: "Verbatim echo, then fresh solution"}, {id: "disclosure-paraphrase", label: "Paraphrase, then fresh solution"}, {id: "disclosure-struggle", label: "Still needs help after disclosure"}], respond: echo,
  }, {
    id: "misconception", label: "Misconception and correction", personas: [13, 14], blockTypes: ["worked_example", "retrieval_check"], fixture: "Inflation formula, practice and a new topic",
    context: "Use a CPI worked example from 120 to 132. The initial belief confuses points and percent. To exercise the correction, the tutor must show 12 divided by 120 and 10% on a retry. A later recall in this component can ask who wrote Romeo and Juliet. Original always-right and always-wrong controls remain available under Rule-led.",
    variants: [{id: "cpi-belief-revises", label: "Revises belief after correction"}, {id: "cpi-belief-persists", label: "Persists after correction"}], respond: misconception,
  }, {
    id: "closing", label: "Acknowledgement, continuation and stopping", personas: [3, 7], blockTypes: ["explanation", "topic_goal", "retrieval_check"], fixture: "Inflation formula, practice and a new topic (retrieval summary)",
    context: "At the block summary compare an acknowledgement, the displayed Continue action, a request to be quizzed, or two short replies followed by a stop request if the tutor keeps the exchange open.",
    variants: [{id: "closing-acknowledges", label: "Brief acknowledgement"}, {id: "closing-continue", label: "Explicit Continue button"},
      {id: "closing-more", label: "Asks for one more question"}, {id: "closing-stops", label: "Repeated k, then asks to stop"}], respond: closing,
  }, {
    id: "aside", label: "Aside and return to task", personas: [4, 12], blockTypes: ["curiosity", "spot_the_flaw", "mcq"], fixture: "Predict what happens to ice, Find the wrong total, or Inflation choice and reasoning",
    context: "Offer the aside on a typed prediction or critique and inspect the next tutoring turn. On a choice-only MCQ both variants select the first visible option, as the real child cannot type an aside there.",
    variants: [{id: "aside-interest", label: "Harmless pet aside"}, {id: "aside-identity", label: "Fictional tutor identity question"}],
    respond(id, input) {
      if (input.substep === "choice" && input.blockType === "mcq" && !input.canType) {
        const first = input.choices[0];
        if (first && !alreadySaid(input, first.text)) return first.text;
      }
      if (!["hook_and_predict", "critique"].includes(input.substep)) return;
      const line = id === "aside-interest" ? "My cat just sat on my notebook!" : "Are you a person or a computer tutor?";
      return typedOnce(input, line);
    },
  }, {
    id: "reason", label: "Clarification, partial reasoning and guessing", personas: [1, 6], blockTypes: CPI_NUMBER_TYPES, fixture: "Inflation formula, practice and a new topic (typed) or Inflation choice and reasoning (choice)",
    context: "Use the same CPI change from 120 to 132. On a typed solo or transfer step, compare a definition request and a partial calculation. On an MCQ include a visible 10% choice and require a why follow-up. Inspect the lucky guess and, if the tutor asks again, its repair.",
    variants: [{id: "reason-clarify", label: "Asks for a definition"}, {id: "reason-partial", label: "Partial answer with follow-up"},
      {id: "reason-guess", label: "Correct choice, wrong reason, then repair"}, {id: "reason-sound", label: "Same choice, sound reason"}], respond: clarify,
  },
];

export function findHarnessScenario(id: string) {
  for (const group of SCENARIO_GROUPS) {
    const variant = group.variants.find(item => item.id === id);
    if (variant) return { group, variant };
  }
}

export function scenarioMove(id: string, input: ScenarioInput): string | undefined {
  const scenario = findHarnessScenario(id);
  if (!scenario || !scenario.group.personas.includes(input.personaNumber) || !scenario.group.blockTypes.includes(input.blockType)) return;
  return scenario.group.respond(id, input);
}
