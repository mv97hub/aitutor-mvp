/** Turn harness findings plus stored prompts into review cards.

The cards quote sentences that are already in the stored tutor prompt and name
the prompt-builder section and function that wrote them. Nothing here edits
kc_prompt.py or applies a setting.
*/

import { type RecommendationCard } from "./harness.ts";

export const RECOMMENDATION_DOC =
  "/cursor/stores/bc-755f27de-cf8f-4751-bc70-3f161bf28a51/docs/harness-prompt-recommendations.md";

export type DraftFinding = {
  title?: string;
  tag?: string;
  block_label?: string;
  count?: number;
  cause_class?: string;
  place?: string;
  run_id?: string;
  examples?: { chat_id?: string; turn?: number; block?: string; child?: string; run_id?: string }[];
  nudges?: StuckNudge[];
};

export type StuckNudge = {
  turn?: number;
  asked?: string;
  answered?: string;
  block_type?: string;
  block_id?: string;
  substep?: string;
  child?: string;
  run_id?: string;
};

export type DraftSource = {
  run_id?: string;
  turn?: number;
  block_type?: string;
  chat_id?: string;
};

export type BuilderExcerpt = {
  symbol: string;
  section: string;
  function: string;
  source: string;
  literals?: string[];
};

export type ExampleTurn = {
  chat_id?: string;
  turn?: number;
  intent?: string;
  child_text?: string;
  block_label?: string;
  tutor_prompt?: string;
  sections?: Record<string, string>;
  run_id?: string;
};

export type DraftMaterials = {
  run_id?: string;
  findings?: DraftFinding[] | { findings?: DraftFinding[] };
  examples?: ExampleTurn[];
  builder?: BuilderExcerpt[];
  runs?: DraftMaterials[];
};

export type DraftEvidence = {
  summary?: string;
  block_type?: string;
  section?: string;
  function?: string;
  symbol?: string;
  current?: string;
  replacement?: string;
  shorter?: string;
  nudges?: StuckNudge[];
  sources?: DraftSource[];
  findings?: { tag?: string; title?: string }[];
};

export type DraftCard = RecommendationCard & {
  evidence: DraftEvidence;
  proposed: { text: string; shorter: string };
};

export type ModelDraft = {
  current_quote?: string;
  replacement?: string;
  shorter?: string;
  evidence_summary?: string;
};

const TAG_SYMBOLS: Record<string, string[]> = {
  stuck: ["_GOAL_START_DEEPEN", "_GOAL_START_EXPLAIN", "_GOAL_START_ASIDE", "_how_to_teach"],
  one_question: ["_GOAL_START_DEEPEN", "_GOAL_START_EXPLAIN", "_GOAL_START_ASK", "_GOAL_START_ASIDE", "_how_to_teach"],
  stay_on_course: ["_GOAL_START_ASIDE", "_GOAL_START_CLARIFY", "_SIDE_STAY", "_how_to_teach"],
  repeated_itself: ["_block_config_rules", "_how_to_teach", "_this_turn"],
  ignored_question: ["_GOAL_START_ASIDE", "_GOAL_START_CLARIFY", "_SIDE_STAY"],
};

// Old stored prompts say "more deeply". The current Tell me more line says
// "still on the explanation" and "from a fresh angle".
const STUCK_LINE = /more deeply|still on the explanation|from a fresh angle/;

const TAG_PREFER: Record<string, RegExp> = {
  stuck: new RegExp(`${STUCK_LINE.source}|why it matters|do not ask any question`),
  one_question: /do not ask any question|one question/,
  stay_on_course: /side remark|question they typed/,
  repeated_itself: /nudge|hint|missed answer/,
  ignored_question: /question they typed|side remark|answer that question/,
};

export function nudgeSentences(nudges: StuckNudge[], block: string): string[] {
  return nudges.map((nudge) => {
    const named = nudge.block_type || block || "an unknown block";
    const place = [nudge.block_id, nudge.substep].filter(Boolean).join(" / ");
    const where = place ? `${named} (${place})` : named;
    return `Turn ${nudge.turn ?? ""}: the child asked "${nudge.asked || ""}". The tutor answered "${nudge.answered || ""}". ${where} did not move.`;
  });
}

export function fold(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

export function findingsOf(materials: DraftMaterials): DraftFinding[] {
  const raw = materials.findings;
  if (Array.isArray(raw)) return raw.filter((item) => item && typeof item === "object");
  if (raw && Array.isArray(raw.findings)) return raw.findings.filter((item) => item && typeof item === "object");
  return [];
}

export const RECENT_RUN_PICKS = 3;

export function defaultSelectedRunIds(runIds: string[], count = RECENT_RUN_PICKS): string[] {
  return runIds.filter(Boolean).slice(0, count);
}

export function skippedRunMessage(failures: { runId: string; message: string }[]): string {
  const named = failures
    .filter((item) => item.runId)
    .map((item) => `${item.runId}: ${item.message || "Could not read this run."}`);
  if (named.length === 0) return "";
  return `Could not read ${named.join("; ")}. The other selected runs were still drafted.`;
}

export function materialsFromRuns(runs: DraftMaterials[]): DraftMaterials {
  const findings: DraftFinding[] = [];
  const examples: ExampleTurn[] = [];
  let builder: BuilderExcerpt[] = [];
  const ids: string[] = [];
  for (const run of runs) {
    const runId = String(run.run_id || "");
    if (runId) ids.push(runId);
    if (builder.length === 0 && run.builder && run.builder.length > 0) builder = run.builder;
    for (const finding of findingsOf(run)) {
      findings.push({
        ...finding,
        run_id: finding.run_id || runId,
        nudges: (finding.nudges || []).map((nudge) => ({ ...nudge, run_id: nudge.run_id || runId })),
        examples: (finding.examples || []).map((example) => ({ ...example, run_id: example.run_id || runId })),
      });
    }
    for (const example of run.examples || []) {
      examples.push({ ...example, run_id: example.run_id || runId });
    }
  }
  return { run_id: ids.join(","), findings, examples, builder };
}

export function flattenMaterials(materials: DraftMaterials): DraftMaterials {
  if (materials.runs && materials.runs.length > 0) return materialsFromRuns(materials.runs);
  return materialsFromRuns([materials]);
}

function namedBlock(value?: string): string {
  const text = (value || "").trim();
  if (!text || text === "an unknown block") return "";
  return text;
}

function uniqueText(values: string[]): string[] {
  const seen: string[] = [];
  for (const value of values) {
    const text = value.trim();
    if (text && !seen.includes(text)) seen.push(text);
  }
  return seen;
}

export function sourceSentences(sources: DraftSource[]): string[] {
  return sources.map((source) => {
    const run = source.run_id || "an unknown run";
    const turn = source.turn === undefined || source.turn === null ? "" : ` turn ${source.turn}`;
    const block = source.block_type || "an unknown block";
    return `Run ${run}${turn}, ${block}.`;
  });
}

function sentences(text: string): string[] {
  return fold(text)
    .split(/(?<=[.!?])\s+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 20);
}

function appearsIn(prompt: string, sentence: string): boolean {
  const needle = fold(sentence).toLowerCase();
  if (needle.length < 20) return false;
  return fold(prompt).toLowerCase().includes(needle);
}

function quoteFromPrompt(prompt: string, sentence: string): string {
  const folded = fold(sentence);
  if (prompt.includes(sentence)) return sentence;
  if (prompt.includes(folded)) return folded;
  if (appearsIn(prompt, folded)) return folded;
  return "";
}

function literalsOf(excerpt: BuilderExcerpt): string[] {
  if (excerpt.literals && excerpt.literals.length > 0) return excerpt.literals;
  const found: string[] = [];
  const pattern = /"([^"\\]|\\.){40,}"|'([^'\\]|\\.){40,}'/g;
  for (const match of excerpt.source.matchAll(pattern)) {
    const raw = match[0].slice(1, -1);
    if (raw) found.push(fold(raw));
  }
  return found;
}

function scoreLiteral(tag: string, literal: string): number {
  const text = literal.toLowerCase();
  const prefer = TAG_PREFER[tag];
  let score = Math.min(literal.length, 400);
  if (prefer && prefer.test(text)) score += 2000;
  if (tag === "one_question" && text.includes("side remark")) score -= 800;
  if (tag === "stuck" && STUCK_LINE.test(text)) score += 400;
  return score;
}

function pickQuote(
  tag: string,
  excerpts: BuilderExcerpt[],
  prompts: string[],
): { excerpt: BuilderExcerpt; current: string } | null {
  const symbols = new Set(TAG_SYMBOLS[tag] || []);
  let best: { excerpt: BuilderExcerpt; current: string; score: number } | null = null;
  for (const excerpt of excerpts) {
    for (const literal of literalsOf(excerpt)) {
      for (const prompt of prompts) {
        const current = quoteFromPrompt(prompt, literal);
        if (!current) continue;
        let score = scoreLiteral(tag, literal);
        if (symbols.size === 0 || symbols.has(excerpt.symbol)) score += 500;
        if (!best || score > best.score) best = { excerpt, current, score };
      }
    }
  }
  return best ? { excerpt: best.excerpt, current: best.current } : null;
}

function propose(tag: string, current: string): { replacement: string; shorter: string; kind: DraftCard["kind"] } {
  const text = current.toLowerCase();
  if (tag === "repeated_itself" || /nudge|those hints|missed answers/.test(text)) {
    return {
      replacement: "On a goal-start turn, do not climb the hint ladder and do not repeat the last explanation. Answer once.",
      shorter: "Remove this sentence.",
      kind: "remove",
    };
  }
  if (tag === "one_question") {
    if (text.includes("side remark") || text.includes("question they typed")) {
      return {
        replacement: "Answer the side remark in one sentence, then one line back to the lesson. Ask no question. One question waits until the learner moves on.",
        shorter: "Answer in one sentence. Ask no question.",
        kind: "reword",
      };
    }
    return {
      replacement: "Explain this topic in two or three sentences, then stop. Ask no question. One question waits until the learner moves on.",
      shorter: "Ask no question.",
      kind: "reword",
    };
  }
  if (tag === "stay_on_course") {
    return {
      replacement: "Stay on course: answer in one sentence, then one line back to this block. Do not ask a question.",
      shorter: "Stay on course: one sentence, then back to this block.",
      kind: "reword",
    };
  }
  if (tag === "ignored_question") {
    return {
      replacement: "Answer the question they typed in one sentence, then one line back to the lesson.",
      shorter: "Answer their question in one sentence.",
      kind: "reword",
    };
  }
  if (/side remark/.test(text)) {
    return {
      replacement: "Answer the side remark in one sentence, then one line back to the lesson. Do not start a new explanation. Do not ask a question.",
      shorter: "One sentence on the side remark, then stop.",
      kind: "reword",
    };
  }
  return {
    replacement: "Explain this topic in two or three sentences, then stop. The learner leaves this step with Got it - move on. Ask no question.",
    shorter: "Explain this topic in two sentences, then stop.",
    kind: "reword",
  };
}

function sectionText(example: ExampleTurn, name: string): string {
  return example.sections?.[name] || "";
}

function duplicateSentence(examples: ExampleTurn[]): { prompt: string; sentence: string } | null {
  for (const example of examples) {
    const turn = sectionText(example, "This turn") || example.tutor_prompt || "";
    const teach = sectionText(example, "How to teach");
    if (!turn || !teach) continue;
    const turnFold = fold(turn).toLowerCase();
    for (const sentence of sentences(teach)) {
      if (sentence.length < 40) continue;
      if (turnFold.includes(fold(sentence).toLowerCase())) {
        return { prompt: example.tutor_prompt || teach, sentence: quoteFromPrompt(example.tutor_prompt || teach, sentence) || sentence };
      }
    }
  }
  return null;
}

function cardFrom(input: {
  block: string;
  findings: DraftFinding[];
  excerpt: BuilderExcerpt;
  current: string;
  replacement: string;
  shorter: string;
  kind: DraftCard["kind"];
  title: string;
  sources: DraftSource[];
  nudges: StuckNudge[];
}): DraftCard {
  const place = `${input.excerpt.section} — ${input.excerpt.function}${
    input.excerpt.symbol !== input.excerpt.function ? ` (${input.excerpt.symbol})` : ""
  }`;
  const listed = input.findings.map((finding) => ({
    tag: finding.tag || "",
    title: finding.title || finding.tag || "Finding",
  }));
  const findingLine = listed.map((finding) => finding.title).filter(Boolean).join("; ");
  const nudgeLines = nudgeSentences(input.nudges, input.block);
  const summary = [
    findingLine ? `Findings: ${findingLine}.` : "",
    `${input.excerpt.section} is written by ${input.excerpt.function} in kc_prompt.py.`,
    input.excerpt.symbol !== input.excerpt.function ? `The sentence is ${input.excerpt.symbol}.` : "",
    ...sourceSentences(input.sources),
    "The quoted line is taken from the stored tutor prompt of each evidence turn. One replacement covers every finding on this line. Nothing here changes the live tutor.",
    ...nudgeLines,
  ]
    .filter(Boolean)
    .join(" ");
  const cause = input.findings.find((finding) => finding.cause_class)?.cause_class || "prompt";
  return {
    title: input.title.slice(0, 200),
    cause_class: cause,
    place,
    kind: input.kind,
    prompt_direction: "shorter",
    risk: "A shorter line can drop a reminder the tutor was using. Read the quote before editing the prompt builder.",
    confidence: "high",
    block_type: input.block,
    proposed: { text: input.replacement, shorter: input.shorter },
    evidence: {
      summary,
      block_type: input.block,
      section: input.excerpt.section,
      function: input.excerpt.function,
      symbol: input.excerpt.symbol,
      current: input.current,
      replacement: input.replacement,
      shorter: input.shorter,
      nudges: nudgeLines.length ? input.nudges : undefined,
      sources: input.sources.length ? input.sources : undefined,
      findings: listed,
    },
  };
}

type LineHit = {
  finding: DraftFinding;
  excerpt: BuilderExcerpt;
  current: string;
  turns: ExampleTurn[];
};

function lineKey(excerpt: BuilderExcerpt, current: string): string {
  return `${excerpt.section}\n${excerpt.function}\n${fold(current)}`;
}

function evidenceTurns(finding: DraftFinding, examples: ExampleTurn[]): ExampleTurn[] {
  const runId = finding.run_id || "";
  const pool = examples.filter((item) => item.tutor_prompt && (!runId || !item.run_id || item.run_id === runId));
  const listed = finding.examples || [];
  if (listed.length > 0) {
    const chats = new Set(listed.map((item) => item.chat_id).filter(Boolean));
    const turns = new Set(listed.map((item) => Number(item.turn)).filter((turn) => !Number.isNaN(turn)));
    return pool.filter((item) => {
      if (item.chat_id && chats.size > 0 && !chats.has(item.chat_id)) return false;
      if (turns.size === 0) return true;
      return turns.has(Number(item.turn));
    });
  }
  const block = namedBlock(finding.block_label);
  if (!block) return [];
  return pool.filter((item) => namedBlock(item.block_label) === block);
}

function tagFit(tag: string, current: string): number {
  let score = scoreLiteral(tag, current);
  if (tag === "duplicate") score += 1500;
  if (tag === "repeated_itself" && /nudge|those hints|missed answers/.test(current.toLowerCase())) score += 3000;
  return score;
}

function replacementFor(current: string, tags: string[]): { replacement: string; shorter: string; kind: DraftCard["kind"] } {
  const ranked = [...tags].sort((a, b) => tagFit(b, current) - tagFit(a, current) || a.localeCompare(b));
  return propose(ranked[0] || "", current);
}

function pushHit(groups: Map<string, LineHit[]>, hit: LineHit) {
  const key = lineKey(hit.excerpt, hit.current);
  const list = groups.get(key) || [];
  list.push(hit);
  groups.set(key, list);
}

function sourceKey(source: DraftSource): string {
  return `${source.run_id || ""}|${source.chat_id || ""}|${source.turn ?? ""}|${source.block_type || ""}`;
}

function nudgeKey(nudge: StuckNudge, runId: string): string {
  return `${nudge.run_id || runId}|${nudge.turn ?? ""}|${nudge.asked || ""}|${nudge.block_type || ""}`;
}

function draftFlatCards(materials: DraftMaterials): DraftCard[] {
  const findings = findingsOf(materials);
  const examples = materials.examples || [];
  const builder = materials.builder || [];
  const groups = new Map<string, LineHit[]>();
  for (const finding of findings) {
    const turns = evidenceTurns(finding, examples);
    const picked = pickQuote(String(finding.tag || ""), builder, turns.map((turn) => turn.tutor_prompt || ""));
    if (!picked) continue;
    const containing = turns.filter((turn) => appearsIn(turn.tutor_prompt || "", picked.current));
    if (containing.length === 0) continue;
    const current = quoteFromPrompt(containing[0].tutor_prompt || "", picked.current) || picked.current;
    pushHit(groups, { finding, excerpt: picked.excerpt, current, turns: containing });
  }
  const teach = builder.find((item) => item.function === "_how_to_teach" && item.section === "How to teach");
  if (teach) {
    for (const example of examples) {
      const duplicate = duplicateSentence([example]);
      if (!duplicate?.sentence || !appearsIn(example.tutor_prompt || "", duplicate.sentence)) continue;
      const current = quoteFromPrompt(example.tutor_prompt || "", duplicate.sentence) || duplicate.sentence;
      pushHit(groups, {
        finding: {
          title: "The same sentence is in This turn and How to teach",
          tag: "duplicate",
          cause_class: "prompt",
          run_id: example.run_id,
          block_label: example.block_label,
        },
        excerpt: teach,
        current,
        turns: [example],
      });
    }
  }
  const seenNudges = new Set<string>();
  const cards: DraftCard[] = [];
  for (const hits of groups.values()) {
    const excerpt = hits[0].excerpt;
    const current = hits[0].current;
    const findings: DraftFinding[] = [];
    const seenFindings = new Set<string>();
    for (const hit of hits) {
      const mark = `${hit.finding.tag || ""}|${hit.finding.title || ""}|${hit.finding.run_id || ""}`;
      if (seenFindings.has(mark)) continue;
      seenFindings.add(mark);
      findings.push(hit.finding);
    }
    const tags = uniqueText(findings.map((finding) => finding.tag || finding.title || "finding"));
    const next = replacementFor(current, tags);
    const sources: DraftSource[] = [];
    const seenSources = new Set<string>();
    for (const hit of hits) {
      for (const turn of hit.turns) {
        if (!appearsIn(turn.tutor_prompt || "", current)) continue;
        const source: DraftSource = {
          run_id: turn.run_id || hit.finding.run_id,
          turn: turn.turn,
          block_type: namedBlock(turn.block_label),
          chat_id: turn.chat_id,
        };
        const key = sourceKey(source);
        if (seenSources.has(key)) continue;
        seenSources.add(key);
        sources.push(source);
      }
    }
    if (sources.length === 0) continue;
    const blocks = uniqueText(sources.map((source) => source.block_type || ""));
    const block = blocks.length ? blocks.join(", ") : "an unknown block";
    const nudges: StuckNudge[] = [];
    for (const hit of hits) {
      if (hit.finding.tag !== "stuck") continue;
      for (const nudge of hit.finding.nudges || []) {
        const key = nudgeKey(nudge, hit.finding.run_id || "");
        if (seenNudges.has(key)) continue;
        const nudgeBlock = namedBlock(nudge.block_type);
        if (nudgeBlock && blocks.length > 0 && !blocks.includes(nudgeBlock)) continue;
        seenNudges.add(key);
        nudges.push({ ...nudge, run_id: nudge.run_id || hit.finding.run_id });
      }
    }
    const labels = tags.map((tag) => tag.replaceAll("_", " "));
    cards.push(
      cardFrom({
        block,
        findings,
        excerpt,
        current,
        replacement: next.replacement,
        shorter: next.shorter,
        kind: next.kind,
        title: `${block}: ${excerpt.section} (${excerpt.function}) — ${labels.join(", ")}`,
        sources,
        nudges,
      }),
    );
  }
  return cards;
}

export function draftPromptCards(materials: DraftMaterials): DraftCard[] {
  return draftFlatCards(flattenMaterials(materials));
}

export function prepareDraft(materials: DraftMaterials): { materials: DraftMaterials; cards: DraftCard[] } {
  const flat = flattenMaterials(materials);
  return { materials: flat, cards: draftFlatCards(flat) };
}

export function applyModelReplacements(cards: DraftCard[], modelCards: ModelDraft[]): DraftCard[] {
  return cards.map((card) => {
    const current = fold(card.evidence.current || "");
    const match = modelCards.find((item) => {
      if (fold(item.current_quote || "") !== current) return false;
      const replacement = (item.replacement || "").trim();
      return Boolean(replacement) && fold(replacement).length < current.length;
    });
    if (!match) return card;
    const replacement = (match.replacement || "").trim();
    const shorter = (match.shorter || "").trim();
    return {
      ...card,
      proposed: { text: replacement, shorter: shorter || card.proposed.shorter },
      evidence: {
        ...card.evidence,
        replacement,
        shorter: shorter || card.evidence.shorter,
        summary: match.evidence_summary?.trim() || card.evidence.summary,
      },
    };
  });
}

export function drafterPrompt(materials: DraftMaterials, cards: DraftCard[]): string {
  const excerpts = (materials.builder || [])
    .filter((item) => cards.some((card) => card.evidence.symbol === item.symbol || card.evidence.function === item.function))
    .map((item) => `### ${item.section} · ${item.function} · ${item.symbol}\n${item.source}`)
    .join("\n\n");
  const stored = (materials.examples || [])
    .slice(0, 4)
    .map((example, index) => {
      const sections = ["This turn", "How to teach", "What to return"]
        .map((name) => (example.sections?.[name] ? `${name}\n${example.sections[name]}` : ""))
        .filter(Boolean)
        .join("\n\n");
      return `Example ${index + 1} turn ${example.turn ?? ""} chat ${example.chat_id ?? ""}\nChild: ${example.child_text || ""}\n${sections || example.tutor_prompt || ""}`;
    })
    .join("\n\n");
  const quoted = cards
    .map(
      (card, index) =>
        `${index}. section ${card.evidence.section}; function ${card.evidence.function}; current_quote: ${card.evidence.current}`,
    )
    .join("\n");
  return [
    "Rewrite the replacement for each card. A person reviews every card. Do not edit the live prompt builder.",
    "current_quote is an exact sentence from the stored tutor prompt. Repeat it unchanged.",
    "replacement replaces those sentences. shorter is a shorter sentence, or Remove this sentence, when cutting the line fixes the finding.",
    "Prefer the shorter or removed line over adding a new paragraph.",
    `Cards:\n${quoted}`,
    `Prompt builder source:\n${excerpts}`,
    `Stored prompts for the example turns:\n${stored}`,
  ].join("\n\n");
}

function runList(runId: string): string {
  const ids = (runId || "").split(",").map((id) => id.trim()).filter(Boolean);
  if (ids.length === 0) return "`unknown`";
  return ids.map((id) => "`" + id + "`").join(", ");
}

export type SummaryCard = {
  title?: string;
  evidence?: {
    block_type?: string;
    section?: string;
    function?: string;
    current?: string;
    shorter?: string;
    sources?: DraftSource[];
    nudges?: StuckNudge[];
    findings?: { tag?: string; title?: string }[];
  };
  proposed?: { text?: string; shorter?: string };
};

/** Plain text for a later Cursor run. Built only from the cards already on the page. */
export function recommendationPageSummary(cards: SummaryCard[]): string {
  const lines = [
    "Harness recommendation summary",
    "",
    "This text is for a later Cursor run. The harness does not change the live tutor prompt, and it does not edit apps/api/app/kc_prompt.py.",
    "",
  ];
  cards.forEach((card, index) => {
    const evidence = card.evidence || {};
    const shorter = (evidence.shorter || card.proposed?.shorter || "").trim();
    lines.push(`Theme ${index + 1}: ${card.title || "Recommendation"}`);
    const findingNames = (evidence.findings || []).map((finding) => finding.title || finding.tag || "").filter(Boolean);
    if (findingNames.length > 0) lines.push(`Findings: ${findingNames.join("; ")}`);
    lines.push(`Section: ${evidence.section || "unknown"}`);
    lines.push(`Function: ${evidence.function || "unknown"}`);
    lines.push(`Quoted stored line: ${evidence.current || ""}`);
    lines.push(`Shorter replacement: ${shorter}`);
    const sources = evidence.sources || [];
    if (sources.length === 0) {
      lines.push(`Evidence: block type ${evidence.block_type || "an unknown block"}.`);
    } else {
      for (const source of sources) {
        const block = source.block_type || evidence.block_type || "an unknown block";
        const turn = source.turn === undefined || source.turn === null ? "unknown" : String(source.turn);
        lines.push(`Evidence: block type ${block}. Run ${source.run_id || "unknown"}. Turn ${turn}.`);
      }
    }
    for (const sentence of nudgeSentences(evidence.nudges || [], evidence.block_type || "")) {
      lines.push(`Stuck nudge: ${sentence}`);
    }
    lines.push("");
  });
  return lines.join("\n").trim();
}

export function recommendationMarkdown(runId: string, cards: DraftCard[]): string {
  const lines = [
    "# Harness prompt recommendations",
    "",
    "Runs: " + runList(runId),
    "",
    "These cards are prompt-tuning instructions for a later Cursor run. Drafting does not change the live tutor and does not edit `apps/api/app/kc_prompt.py`. Apply a card only when a person asks.",
    "",
  ];
  cards.forEach((card, index) => {
    lines.push(`## ${index + 1}. ${card.title}`);
    lines.push("");
    lines.push(`- Block type: ${card.evidence.block_type || "an unknown block"}`);
    for (const source of card.evidence.sources || []) {
      lines.push(`- Run \`${source.run_id || ""}\`, turn ${source.turn ?? ""}, ${source.block_type || card.evidence.block_type || "an unknown block"}`);
    }
    lines.push(`- Section: ${card.evidence.section || ""}`);
    lines.push(`- Function: \`${card.evidence.function || ""}\`${card.evidence.symbol && card.evidence.symbol !== card.evidence.function ? ` (\`${card.evidence.symbol}\`)` : ""}`);
    lines.push(`- Kind: ${card.kind}, prompt gets ${card.prompt_direction}`);
    lines.push(`- Place: ${card.place || ""}`);
    lines.push("");
    lines.push(card.evidence.summary || "");
    lines.push("");
    if (card.evidence.nudges && card.evidence.nudges.length > 0) {
      lines.push("### Nudges");
      lines.push("");
      for (const sentence of nudgeSentences(card.evidence.nudges, card.evidence.block_type || "")) {
        lines.push(`- ${sentence}`);
      }
      lines.push("");
    }
    lines.push("### Current sentences");
    lines.push("");
    lines.push(`> ${card.evidence.current || ""}`);
    lines.push("");
    lines.push("### Replacement");
    lines.push("");
    lines.push(card.evidence.replacement || card.proposed.text || "");
    lines.push("");
    lines.push("### Shorter or removed");
    lines.push("");
    lines.push(card.evidence.shorter || card.proposed.shorter || "");
    lines.push("");
  });
  return lines.join("\n");
}

