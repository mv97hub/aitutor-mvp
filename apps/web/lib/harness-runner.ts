/** One chat in the open tab. Turns are one after another. Several chats can run side by side. */

import { availableActions } from "./harness-actions.ts";
import { EMPTY_INNER, holdQuit, pickMove, updateInner, type InnerState, type Traits } from "./harness-policy.ts";

export type RunStatus = { status: string };

export type SessionSnap = {
  id: string;
  status: string;
  needs_speech: boolean;
  active_block_type?: string;
  active_substep?: string;
  active_block_index?: number;
  choice?: { prompt: string; choices: { id: string; text: string }[] } | null;
  messages: { role: string; content: string }[];
  block_id?: string;
  move_attempts?: number;
  prompt?: string;
  safety_flag?: string;
  passed?: boolean;
};

export type ClaimedChat = {
  id: string;
  session_id: string;
  tutor_model: string;
  child_model: string;
  behavior: "rule" | "free" | "script";
  seed: number;
  script?: string[];
  child: { description?: string; traits?: Traits; child_profile?: { interests?: string } };
};

export type TurnRecord = {
  stop: string;
  cost_usd: string | null;
  luna_tokens: number;
};

export type HarnessTransport = {
  runStatus: () => Promise<RunStatus>;
  session: (sessionId: string) => Promise<SessionSnap>;
  speak: (sessionId: string, model: string) => Promise<SessionSnap>;
  answer: (sessionId: string, text: string, model: string) => Promise<SessionSnap>;
  answerKey: (chatId: string) => Promise<{
    expected?: string;
    correct_choice_id?: string;
    misconceptions?: { wrong_move?: string }[];
    probes?: string[];
    choices?: { id: string; text: string; correct?: boolean }[];
    block_id?: string;
    block_type?: string;
    move_attempts?: number;
  }>;
  childText: (input: {
    model: string;
    intent: string;
    description: string;
    traits: Traits;
    expected?: string;
    wrongMove?: string;
    lastTutor: string;
    interests?: string;
  }) => Promise<{ text: string; input_tokens: number; output_tokens: number; model: string; prompt?: string }>;
  recordTurn: (chatId: string, body: Record<string, unknown>) => Promise<TurnRecord>;
  finish: (chatId: string, reason: string) => Promise<void>;
};

function lastTutor(session: SessionSnap): string {
  const message = [...session.messages].reverse().find((item) => item.role === "assistant");
  return message?.content ?? "";
}

function placeOf(
  session: SessionSnap,
  key?: { block_id?: string; block_type?: string; move_attempts?: number },
): Record<string, unknown> {
  return {
    status: session.status,
    block_id: key?.block_id || session.block_id || String(session.active_block_index ?? ""),
    block_type: key?.block_type || session.active_block_type || "",
    substep: session.active_substep || "",
    move_attempts: key?.move_attempts ?? session.move_attempts ?? 0,
    tutor_reply: lastTutor(session),
    prompt: session.prompt || "",
    safety_flag: session.safety_flag || "none",
    passed: Boolean(session.passed) || session.status === "completed",
  };
}

export type LiveLine = { chatId: string; role: "tutor" | "child"; text: string };

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

export async function playChat(
  chat: ClaimedChat,
  transport: HarnessTransport,
  signal?: { aborted: boolean },
  onLive?: (line: LiveLine) => void,
): Promise<"done" | "paused"> {
  let session = await transport.session(chat.session_id);
  const seen = new Set<string>();
  emitNew(seen, session, chat.id, onLive);
  let inner: InnerState = { ...EMPTY_INNER };
  let errors = 0;
  let turn = 0;
  let previousPlace = "";
  const traits = chat.child.traits ?? {};
  while (!signal?.aborted) {
    const run = await transport.runStatus();
    if (run.status === "paused" || run.status === "cancelled") return "paused";
    if (session.needs_speech) {
      try {
        session = await transport.speak(session.id, chat.tutor_model);
        emitNew(seen, session, chat.id, onLive);
        errors = 0;
      } catch {
        errors += 1;
        if (errors >= 2) {
          await transport.finish(chat.id, "route_error");
          return "done";
        }
      }
      continue;
    }
    if (session.status === "completed") {
      await transport.finish(chat.id, "completed");
      return "done";
    }
    const key = await transport.answerKey(chat.id);
    const answerKey = key as { block_type?: string; block_id?: string; move_attempts?: number };
    const actions = availableActions(session);
    if (key.choices && key.choices.length > 0 && actions.choices.length > 0) {
      actions.choices = actions.choices.map((choice) => ({
        ...choice,
        correct: key.choices?.find((item) => item.id === choice.id)?.correct || choice.id === key.correct_choice_id,
      }));
    }
    const tutor = lastTutor(session);
    const move = pickMove({
      traits,
      inner,
      seed: chat.seed,
      turn,
      actions,
      mode: chat.behavior,
      script: chat.script,
      answerKey: key,
      lastTutor: tutor,
      interests: chat.child.child_profile?.interests,
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
        expected: key.expected,
        wrongMove: key.misconceptions?.[0]?.wrong_move,
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
      scripted: chat.behavior === "script",
    });
    intent = held.intent;
    text = held.text;
    if (!text.trim()) text = "ok";
    if (onLive && !seen.has(`child:${text}`)) {
      seen.add(`child:${text}`);
      onLive({ chatId: chat.id, role: "child", text });
    }
    const before = placeOf(session, { ...key, block_type: answerKey.block_type || session.active_block_type });
    let afterSession = session;
    let error = "";
    try {
      afterSession = await transport.answer(session.id, text.slice(0, 2000), chat.tutor_model);
      emitNew(seen, afterSession, chat.id, onLive);
      errors = 0;
    } catch (err) {
      errors += 1;
      error = err instanceof Error ? err.message : "The tutor route failed.";
    }
    const afterKey = error ? key : await transport.answerKey(chat.id).catch(() => key);
    const after = placeOf(afterSession, {
      ...afterKey,
      block_type: (afterKey as { block_type?: string }).block_type || afterSession.active_block_type,
    });
    if (error) after.error = error;
    const place = `${after.block_id}:${after.substep}`;
    inner = updateInner(move.inner, {
      traits,
      tutorMessage: tutor,
      samePlace: previousPlace !== "" && previousPlace === place,
      wrong: move.intent === "answer_wrong" || move.intent === "wrong_choice" || move.intent === "careless_slip",
      usedInterest: Boolean(chat.child.child_profile?.interests) && tutor.toLowerCase().includes(String(chat.child.child_profile?.interests).toLowerCase()),
    });
    if (move.intent === "ask_hint") inner = { ...inner, hints: inner.hints + 1 };
    previousPlace = place;
    const recorded = await transport.recordTurn(chat.id, {
      intent,
      child_text: text,
      child_prompt: childPrompt,
      inner_state: inner,
      session_before: before,
      session_after: after,
      child_tokens: childTokens,
      elapsed_ms: 0,
    });
    turn += 1;
    if (recorded.stop) return "done";
    session = afterSession;
    if (errors >= 2) {
      await transport.finish(chat.id, "route_error");
      return "done";
    }
  }
  return "paused";
}

export async function driveRun(
  runId: string,
  claim: () => Promise<ClaimedChat | null>,
  transport: HarnessTransport,
  concurrency: number,
  signal?: { aborted: boolean },
  onLive?: (line: LiveLine) => void,
): Promise<void> {
  const workers = Array.from({ length: Math.max(1, concurrency) }, async () => {
    while (!signal?.aborted) {
      const run = await transport.runStatus();
      if (run.status === "paused" || run.status === "cancelled" || run.status === "completed") return;
      const chat = await claim();
      if (!chat) return;
      await playChat(chat, transport, signal, onLive);
    }
  });
  await Promise.all(workers);
}
