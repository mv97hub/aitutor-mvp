/** One chat in the open tab. Turns are one after another. Several chats can run side by side. */

import { ApiError } from "./api.ts";
import { findHarnessScenario, scenarioMove } from "./harness-scenarios.ts";
import { availableActions } from "./harness-actions.ts";
import {
  EMPTY_INNER, holdQuit, mulberry32, nudgeAllowed, nudgeTurn, pickMove, soundsLikeQuit, updateInner,
  type InnerState, type SimulationRole, type VisibleLesson, type Traits,
} from "./harness-policy.ts";

export type RunStatus = {
  status: string;
  chat_rows?: { id: string; claim_generation?: number }[];
};

export type SessionSnap = {
  id: string;
  status: string;
  needs_speech: boolean;
  active_block_type?: string;
  active_substep?: string;
  revision?: number;
  actions?: string[] | null;
  active_block_index?: number;
  choice?: { prompt: string; choices: { id: string; text: string }[] } | null;
  messages: { id?: string; role: string; content: string; step?: number }[];
  response_message_id?: string | null;
  tutor_call_kind?: "speak" | "answer";
  block_id?: string;
  move_attempts?: number;
  prompt?: string;
  safety_flag?: string;
  passed?: boolean;
  loop_decision?: string;
  loop_result?: {
    stayed?: boolean;
    advanced?: boolean;
    closed?: string;
    ended_unit?: boolean;
    attempt_counted?: boolean;
  } | null;
  topic_index?: number | null;
};

export type ClaimedChat = {
  id: string;
  session_id: string;
  tutor_model: string;
  child_model: string;
  behavior: "rule" | "free" | "script";
  seed: number;
  script?: string[];
  child: {
    number?: number;
    scenario?: string;
    simulation_role?: SimulationRole;
    description?: string;
    traits?: Traits;
    child_profile?: { interests?: string; reading_level?: string; response_length?: string; expression_style?: string };
  };
  pending_nudges?: number;
  stuck_answers?: number;
  claim_generation?: number;
  pending_turn?: PreparedTurn | null;
  turn_count?: number;
  last_inner_state?: Partial<InnerState>;
  last_place?: string;
};

export type PreparedTurn = {
  turn_id: string;
  revision: number;
  seq: number;
  child_text: string;
  intent: string;
  child_prompt: string;
  child_tokens: { model: string; input_tokens: number; output_tokens: number };
  session_before: Record<string, unknown>;
  move_inner: InnerState;
  move_intent: string;
};

export type TurnRecord = {
  stop: string;
  replayed?: boolean;
  recover?: boolean;
  pending?: boolean;
  pending_nudges?: number;
  stuck_answers?: number;
  cost_usd: string | null;
  luna_tokens: number;
};

export type HarnessTransport = {
  runStatus: () => Promise<RunStatus>;
  session: (sessionId: string) => Promise<SessionSnap>;
  speak: (sessionId: string, model: string) => Promise<SessionSnap>;
  prepareTurn: (chatId: string, generation: number, turn: PreparedTurn) => Promise<PreparedTurn>;
  answer: (sessionId: string, turn: PreparedTurn, model: string) => Promise<SessionSnap>;
  answerKey: (chatId: string) => Promise<{
    revision?: number;
    expected?: string;
    visible_passage?: string;
    correct_choice_id?: string;
    misconceptions?: { wrong_move?: string }[];
    probes?: string[];
    choices?: { id: string; text: string; correct?: boolean }[];
    block_id?: string;
    block_type?: string;
    block_title?: string;
    move_attempts?: number;
    topic_index?: number | null;
  }>;
  childText: (input: {
    model: string;
    intent: string;
    role?: SimulationRole;
    visible?: VisibleLesson;
    description: string;
    traits: Traits;
    expected?: string;
    wrongMove?: string;
    lastTutor: string;
    interests?: string;
  }) => Promise<{ text: string; input_tokens: number; output_tokens: number; model: string; prompt?: string }>;
  recordTurn: (chatId: string, body: Record<string, unknown>) => Promise<TurnRecord>;
  finish: (chatId: string, reason: string, generation?: number) => Promise<void>;
};

function lastTutorMessage(session: SessionSnap) {
  return [...session.messages].reverse().find((item) => item.role === "assistant");
}

function lastTutor(session: SessionSnap): string {
  return lastTutorMessage(session)?.content ?? "";
}

function assistantCount(session: SessionSnap): number {
  return session.messages.filter((item) => item.role === "assistant").length;
}

/** A tutor reply produced by this call. The previous reply is not copied forward. */
function newTutorReply(before: PreparedTurn["session_before"], after: SessionSnap): string | null {
  const latest = lastTutor(after).trim();
  if (!latest) return null;
  const messageId = lastTutorMessage(after)?.id;
  if (after.response_message_id !== undefined && (!messageId || messageId !== after.response_message_id)) return null;
  if (messageId) return before.tutor_message_id === messageId ? null : latest;
  if (assistantCount(after) > Number(before.assistant_count)) return latest;
  if (latest === String(before.tutor_reply || "").trim()) return null;
  return latest;
}

export function placeKey(blockId: unknown, substep: unknown, topic: unknown): string {
  const base = `${blockId ?? ""}:${substep ?? ""}`;
  if (topic === undefined || topic === null || topic === "") return base;
  return `${base}:${topic}`;
}

function topicOf(
  session: SessionSnap,
  key?: { topic_index?: number | null },
): number | null | undefined {
  if (key && "topic_index" in key) return key.topic_index;
  return session.topic_index;
}

function placeOf(
  session: SessionSnap,
  key?: { block_id?: string; block_type?: string; block_title?: string; move_attempts?: number; topic_index?: number | null },
): Record<string, unknown> {
  const topic = topicOf(session, key);
  const loop = session.loop_result;
  const accepted = Boolean(loop && loop.closed !== "revealed" && (loop.closed === "passed" || loop.advanced));
  const row: Record<string, unknown> = {
    status: session.status,
    block_id: key?.block_id || session.block_id || String(session.active_block_index ?? ""),
    block_type: key?.block_type || session.active_block_type || "",
    block_title: key?.block_title || "",
    substep: session.active_substep || "",
    move_attempts: key?.move_attempts ?? session.move_attempts ?? 0,
    tutor_reply: lastTutor(session),
    tutor_message_id: lastTutorMessage(session)?.id ?? null,
    tutor_call_kind: session.tutor_call_kind,
    prompt: session.prompt || "",
    safety_flag: session.safety_flag || "none",
    passed: accepted,
    loop_decision: session.loop_decision || "",
    loop_result: loop ?? null,
  };
  if (topic !== undefined) row.topic_index = topic;
  return row;
}

export type LiveLine = { chatId: string; role: "tutor" | "child"; text: string; seq?: number };

/** The loop keeps going only while this claim still owns the chat. */
export function claimStillOwns(run: RunStatus, chatId: string, generation: number | undefined): boolean {
  if (typeof generation !== "number") return true;
  const row = run.chat_rows?.find((item) => item.id === chatId);
  if (!row || typeof row.claim_generation !== "number") return true;
  return row.claim_generation === generation;
}

function emitNew(seen: Set<string>, session: SessionSnap, chatId: string, onLive?: (line: LiveLine) => void) {
  if (!onLive) return;
  session.messages.forEach((message) => {
    const role = message.role === "assistant" ? "tutor" : "child";
    const key = `${role}:${message.content}`;
    if (seen.has(key)) return;
    seen.add(key);
    onLive({ chatId, role, text: message.content });
  });
}

async function planSubmission(
  chat: ClaimedChat, transport: HarnessTransport, session: SessionSnap, turn: number,
  inner: InnerState, nudgesLeft: number, stuckAnswers: number,
): Promise<PreparedTurn> {
  const traits = chat.child.traits ?? {};
  const key = await transport.answerKey(chat.id);
  const actions = availableActions(session);
  const role = chat.child.simulation_role ?? (chat.behavior === "script" ? "script"
    : chat.behavior === "rule" && [13, 14].includes(chat.child.number ?? 0) ? "answer_key_control" : "learner");
  const tutorMessage = lastTutorMessage(session);
  const tutor = tutorMessage?.content ?? "";
  const target = role === "script" && chat.child.scenario ? findHarnessScenario(chat.child.scenario) : undefined;
  const presetText = target ? scenarioMove(chat.child.scenario!, {
    personaNumber: chat.child.number ?? 0, blockType: session.active_block_type ?? "", substep: session.active_substep ?? "",
    tutor, canType: actions.canType, buttons: actions.buttons, choices: actions.choices,
    question: session.choice?.prompt, history: session.messages, blockIndex: session.active_block_index,
    lastScenarioLine: inner.lastScenarioAction?.blockId === key.block_id ? inner.lastScenarioAction?.text : undefined,
  }) : undefined;
  const policyRole = target && !presetText ? "learner" : role;
  const previous = inner.concepts?.[key.block_id || ""];
  const visible: VisibleLesson = {
    canType: actions.canType, buttons: actions.buttons, choices: actions.choices.map(({ id, text }) => ({ id, text })),
    question: session.choice?.prompt, passage: key.visible_passage,
    recent: session.messages.filter((message) => message !== tutorMessage).slice(-4).map(({ role, content }) => ({ role, content })),
    previousHelpRequests: previous?.helpRequests,
    readingLevel: chat.child.child_profile?.reading_level,
    responseLength: chat.child.child_profile?.response_length,
    expressionStyle: chat.child.child_profile?.expression_style,
  };
  if (role === "answer_key_control" && key.choices?.length && actions.choices.length) {
    actions.choices = actions.choices.map((choice) => ({
      ...choice,
      correct: key.choices?.find((item) => item.id === choice.id)?.correct || choice.id === key.correct_choice_id,
    }));
  }
  const nudging = actions.canType && nudgeAllowed({
    pending: nudgesLeft,
    answersGiven: stuckAnswers,
    tutor,
    choices: actions.choices.length,
  });
  const presetIntent = presetText && soundsLikeQuit(presetText) ? "quit" as const : "script" as const;
  const move = presetText ? { intent: presetIntent, text: presetText, needsModel: false, inner } : nudging
    ? { ...nudgeTurn(nudgesLeft), inner }
    : pickMove({
        traits,
        inner,
        seed: chat.seed,
        turn,
        actions,
        mode: target ? "rule" : chat.behavior,
        script: chat.script,
        role: policyRole,
        answerKey: role === "answer_key_control" ? key : { probes: key.probes },
        lastTutor: tutor,
        interests: chat.child.child_profile?.interests,
        description: chat.child.description,
      });
  let text = move.text;
  let intent = move.intent;
  let childPrompt = "";
  let childTokens = { input_tokens: 0, output_tokens: 0, model: chat.child_model };
  if (move.needsModel) {
    const written = await transport.childText({
      model: chat.child_model,
      intent: move.intent,
      description: chat.child.description || "",
      traits,
      role: policyRole, visible,
      ...(role === "answer_key_control" ? { expected: key.expected, wrongMove: key.misconceptions?.[0]?.wrong_move } : {}),
      lastTutor: tutor,
      interests: chat.child.child_profile?.interests,
    });
    text = written.text;
    childPrompt = written.prompt || "";
    childTokens = { input_tokens: written.input_tokens, output_tokens: written.output_tokens, model: written.model };
  }
  const held = holdQuit({
    intent,
    text,
    traits,
    inner: move.inner,
    buttons: actions.buttons,
    lastTutor: tutor,
    scripted: chat.behavior === "script" && (!target || Boolean(presetText)),
  });
  intent = held.intent;
  text = held.text;
  let choiceFallback = false;
  if ((role !== "script" || target) && !actions.canType) {
    const proposed = text.trim().toLowerCase();
    const chosen = visible.choices.find(({ id, text }) => [id, text, `${id}. ${text}`].some(
      (label) => label.trim().toLowerCase() === proposed));
    if (chosen) text = chosen.text;
    else if (visible.choices.length) {
      const pick = mulberry32((chat.seed + turn * 997) >>> 0)();
      text = visible.choices[Math.floor(pick * visible.choices.length)].text;
      intent = "choice";
      choiceFallback = true;
    } else if (!visible.buttons.includes(text)) {
      if (!visible.buttons.length) throw new Error("The lesson is waiting for a visible action.");
      text = visible.buttons[0];
    }
  }
  if (!text.trim()) text = "ok";
  const before = placeOf(session, key);
  before.expected = key.expected || ""; // Evaluator-only, never sent to realistic child generation.
  before.planned_intent = move.intent;
  before.simulation_role = role;
  if (target) before.scenario_exercised = Boolean(presetText);
  before.choice_fallback = choiceFallback;
  // Retain a transcript boundary for replay, without copying every previous message.
  before.message_count = session.messages.length;
  before.last_message_id = session.messages.at(-1)?.id ?? null;
  before.assistant_count = assistantCount(session);
  return {
    turn_id: crypto.randomUUID(),
    revision: session.revision ?? 0,
    seq: turn + 1,
    child_text: text.trim().slice(0, 2000).trimEnd(),
    intent,
    child_prompt: childPrompt,
    child_tokens: childTokens,
    session_before: before,
    move_inner: move.inner,
    move_intent: move.intent,
  };
}

/** The server treats these checkpoint and record writes as idempotent. Retry the identical body. */
async function writeWithRetry<T>(write: () => Promise<T>): Promise<T> {
  try {
    return await write();
  } catch (error) {
    if (error instanceof ApiError && error.status < 500) throw error;
    return write();
  }
}

export async function playChat(
  chat: ClaimedChat,
  transport: HarnessTransport,
  signal?: { aborted: boolean },
  onLive?: (line: LiveLine) => void,
): Promise<"done" | "paused"> {
  let session = await transport.session(chat.session_id);
  const seen = new Set<string>();
  emitNew(seen, session, chat.id, onLive);
  let inner: InnerState = { ...EMPTY_INNER, ...chat.last_inner_state };
  let errors = 0;
  let turn = chat.turn_count ?? 0;
  let previousPlace = chat.last_place || "";
  let pending = chat.pending_turn ?? null;
  let recovering = Boolean(pending);
  let attempts = 0;
  let nudgesLeft = Math.max(0, Number(chat.pending_nudges) || 0);
  let stuckAnswers = Math.max(0, Number(chat.stuck_answers) || 0);
  const traits = chat.child.traits ?? {};
  const generation = typeof chat.claim_generation === "number" ? chat.claim_generation : undefined;
  while (!signal?.aborted) {
    const run = await transport.runStatus();
    if (run.status === "paused" || run.status === "cancelled") return "paused";
    if (run.status === "completed") return "done";
    if (!claimStillOwns(run, chat.id, generation)) return "paused";
    if (!pending && session.needs_speech) {
      try {
        session = await transport.speak(session.id, chat.tutor_model);
        emitNew(seen, session, chat.id, onLive);
        errors = 0;
      } catch {
        errors += 1;
        if (errors >= 2) {
          await transport.finish(chat.id, "route_error", generation);
          return "done";
        }
      }
      continue;
    }
    if (!pending && session.status === "completed") {
      await transport.finish(chat.id, "completed", generation);
      return "done";
    }
    if (!pending) {
      const planned = await planSubmission(chat, transport, session, turn, inner, nudgesLeft, stuckAnswers);
      pending = await writeWithRetry(() => transport.prepareTurn(chat.id, generation ?? 0, planned));
    }
    const before = pending.session_before;
    if (onLive && !seen.has(`child:${pending.child_text}`)) {
      seen.add(`child:${pending.child_text}`);
      onLive({ chatId: chat.id, role: "child", text: pending.child_text });
    }
    attempts++;
    let afterSession: SessionSnap | null = null;
    let error = "";
    try {
      afterSession = await transport.answer(chat.session_id, pending, chat.tutor_model);
    } catch (err) {
      if (attempts === 1) {
        recovering = true;
        continue;
      }
      error = err instanceof Error ? err.message : "The tutor route failed.";
    }
    const reply = afterSession && newTutorReply(before, afterSession);
    let after: Record<string, unknown> = { ...before };
    if (afterSession) {
      const key = await transport.answerKey(chat.id).catch(() => undefined);
      const sameRevision = key?.revision === undefined || key.revision === afterSession.revision;
      after = placeOf(afterSession, sameRevision ? key : undefined);
    }
    if (reply && afterSession) {
      after.delivery_status = recovering ? "recovered" : "delivered";
      emitNew(seen, afterSession, chat.id, onLive);
      errors = 0;
    } else {
      errors++;
      Object.assign(after, {
        tutor_reply: "", tutor_message_id: null, tutor_call_kind: undefined, prompt: "",
        loop_decision: "", loop_result: null, passed: false, safety_flag: "none",
        delivery_status: afterSession ? "committed_empty" : "unknown",
        error: error || "The tutor did not write a new reply.",
      });
    }
    const place = placeKey(after.block_id, after.substep, after.topic_index);
    let nextInner = updateInner(pending.move_inner, {
      traits,
      tutorMessage: reply || "",
      samePlace: previousPlace !== "" && previousPlace === place,
      wrong: Boolean(reply && afterSession?.loop_result?.attempt_counted && afterSession.loop_result.stayed),
      usedInterest: Boolean(chat.child.child_profile?.interests) && String(reply || "").toLowerCase().includes(String(chat.child.child_profile?.interests).toLowerCase()),
    });
    const loop = afterSession?.loop_result;
    const attempted = Boolean(reply && loop?.attempt_counted);
    const askedForHelp = Boolean(reply && /\b(hint|clue|some help|help me)\b/i.test(pending.child_text));
    const outcome = !reply || !loop ? "unknown" : loop.closed ? `closed_${loop.closed}` : !attempted ? "unscored"
      : loop.stayed ? "stayed_after_attempt" : loop.advanced ? "advanced_after_attempt" : "attempted";
    after.learner_observation = outcome;
    const block = String(before.block_id || "");
    const concepts = { ...pending.move_inner.concepts };
    if (block && reply) {
      const last = concepts[block] || { attempts: 0, helpRequests: 0 };
      concepts[block] = { attempts: last.attempts + Number(attempted), helpRequests: last.helpRequests + Number(askedForHelp) };
    }
    const lastScenarioAction = before.scenario_exercised && reply && block
      ? { blockId: block, text: pending.child_text } : pending.move_inner.lastScenarioAction;
    nextInner = { ...nextInner, concepts, lastScenarioAction, hints: nextInner.hints + Number(askedForHelp) };
    const body = {
      turn_id: pending.turn_id, seq: pending.seq, claim_generation: generation ?? 0,
      intent: pending.intent, child_text: pending.child_text, child_prompt: pending.child_prompt,
      child_tokens: pending.child_tokens, inner_state: nextInner, session_before: before, session_after: after,
      elapsed_ms: 0, defer: attempts >= 3 && !afterSession,
    };
    const recorded = await writeWithRetry(() => transport.recordTurn(chat.id, body));
    if (recorded.recover && attempts < 3) {
      recovering = true;
      continue;
    }
    if (recorded.pending) return "paused";
    if (recorded.stop) return "done";
    // Only a committed harness turn advances the simulator or selects another child action.
    if (!afterSession) throw new Error("The tutor response still needs recovery.");
    inner = nextInner;
    previousPlace = place;
    turn = pending.seq;
    pending = null;
    recovering = false;
    attempts = 0;
    if (typeof recorded.pending_nudges === "number") nudgesLeft = Math.max(0, recorded.pending_nudges);
    if (typeof recorded.stuck_answers === "number") stuckAnswers = Math.max(0, recorded.stuck_answers);
    session = afterSession;
    if (errors >= 2) {
      await transport.finish(chat.id, "route_error", generation);
      return "done";
    }
  }
  return "paused";
}

/** A failed claim waits this long, then tries again. The 20s API abort is the long wait. */
const CLAIM_RETRY_MS = 50;

function pause(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function driveRun(
  runId: string,
  claim: () => Promise<ClaimedChat | null>,
  transport: HarnessTransport,
  concurrency: number,
  signal?: { aborted: boolean },
  onLive?: (line: LiveLine) => void,
): Promise<void> {
  const slots = Math.max(1, concurrency);

  /** One slot. A failed status check or claim retries. A throw while playing drops the slot so another worker replaces it. */
  async function worker(): Promise<"done" | "dropped"> {
    try {
      while (!signal?.aborted) {
        let run;
        try {
          run = await transport.runStatus();
        } catch {
          if (signal?.aborted) return "done";
          await pause(CLAIM_RETRY_MS);
          continue;
        }
        if (run.status === "paused" || run.status === "cancelled" || run.status === "completed") return "done";
        let chat: ClaimedChat | null;
        try {
          chat = await claim();
        } catch {
          if (signal?.aborted) return "done";
          await pause(CLAIM_RETRY_MS);
          continue;
        }
        if (!chat) return "done";
        await playChat(chat, transport, signal, onLive);
      }
      return "done";
    } catch {
      return "dropped";
    }
  }

  let running = 0;
  await new Promise<void>((resolve) => {
    let closed = false;
    const close = () => {
      if (closed || running > 0) return;
      closed = true;
      resolve();
    };
    const start = () => {
      if (closed || signal?.aborted) {
        close();
        return;
      }
      running += 1;
      void worker().then((result) => {
        running -= 1;
        if (result === "dropped" && !signal?.aborted && !closed) start();
        close();
      });
    };
    for (let slot = 0; slot < slots; slot += 1) start();
    if (running === 0) close();
  });
}
