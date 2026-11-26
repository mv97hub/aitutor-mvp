/** The server loop calls the same tutor routes the page calls. One route, one model call. */

import { api, ApiError } from "./api.ts";
import { newTutorMessageId } from "./tutor-turn.ts";
import type { HarnessTransport, PreparedTurn, RunStatus, SessionSnap } from "./harness-runner.ts";

export type RoutePost = (req: Request) => Promise<Response>;

export type TransportRoutes = {
  speak: RoutePost;
  answer: RoutePost;
  child: RoutePost;
  turn: RoutePost;
  finish: RoutePost;
};

export type TransportIo = {
  runStatus: () => Promise<RunStatus>;
  session: (sessionId: string, committed?: SessionSnap) => Promise<SessionSnap>;
  answerKey: HarnessTransport["answerKey"];
};

function jsonRequest(path: string, body: unknown): Request {
  return new Request(`http://harness.local${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function callRoute(post: RoutePost, path: string, body: unknown): Promise<Response> {
  return post(jsonRequest(path, body));
}

export async function readSnap(sessionId: string, committed?: SessionSnap): Promise<SessionSnap> {
  const session = committed ?? await api<SessionSnap>(`/kc/tutor/sessions/${sessionId}`);
  let prompt = "";
  let safety = session.safety_flag || "none";
  let loop: SessionSnap["loop_result"] = session.loop_result ?? null;
  let loopDecision = session.loop_decision || "";
  try {
    const detail = await api<{
      prompts?: {
        message_id?: string;
        system_prompt?: string;
        decision?: {
          safety_flag?: string;
          loop_result?: SessionSnap["loop_result"];
          loop_decision?: string;
        };
      }[];
    }>(`/kc/sessions/${sessionId}`);
    const messageId = [...session.messages].reverse().find((message) => message.role === "assistant")?.id;
    const matches = messageId ? detail.prompts?.filter((row) => row.message_id === messageId) : [];
    const record = matches?.length === 1 ? matches[0] : undefined;
    prompt = record?.system_prompt || "";
    safety = session.safety_flag || record?.decision?.safety_flag || "none";
    loop ??= record?.decision?.loop_result ?? null;
    loopDecision ||= record?.decision?.loop_decision || "";
  } catch {
    prompt = "";
  }
  const accepted = Boolean(loop && loop.closed !== "revealed" && (loop.closed === "passed" || loop.advanced));
  return {
    ...session,
    id: sessionId,
    prompt,
    safety_flag: safety,
    passed: accepted,
    loop_result: loop,
    loop_decision: loopDecision,
    messages: session.messages || [],
  };
}

export function serverTransport(runId: string, routes: TransportRoutes, io?: TransportIo): HarnessTransport {
  const session = io?.session ?? readSnap;
  async function committedSnap(
    sessionId: string, saved: SessionSnap, kind: "speak" | "answer", messageId: string | null,
  ) {
    return {
      ...await session(sessionId, saved),
      response_message_id: messageId,
      tutor_call_kind: messageId ? kind : undefined,
    };
  }
  return {
    runStatus: io?.runStatus ?? (() => api<RunStatus>(`/kc/harness/runs/${runId}`)),
    session,
    speak: async (sessionId, model) => {
      const prior = await session(sessionId);
      const response = await callRoute(routes.speak, "/api/kc/tutor/speak", {
        sessionId,
        model,
        turnId: crypto.randomUUID(),
        revision: prior.revision ?? 0,
      });
      if (!response.ok) throw new Error((await response.text()) || "The tutor could not speak.");
      const saved: SessionSnap = await response.json();
      return committedSnap(sessionId, saved, "speak", newTutorMessageId(prior.messages, saved.messages));
    },
    prepareTurn: async (chatId, generation, submission) => {
      const saved = await api<{ submission: PreparedTurn }>(`/kc/harness/chats/${chatId}/pending-turn`, {
        method: "POST", body: JSON.stringify({ claim_generation: generation, seq: submission.seq, submission }),
      });
      return saved.submission;
    },
    answer: async (sessionId, pending, model, receiptOnlyChatId) => {
      let saved: SessionSnap;
      if (receiptOnlyChatId) {
        const receipt = await api<{ result: SessionSnap | null }>(
          `/kc/harness/chats/${receiptOnlyChatId}/pending-turn/${pending.turn_id}`,
        );
        if (!receipt.result) throw new Error("The tutor has not committed this submission.");
        saved = receipt.result;
      } else {
        const response = await callRoute(routes.answer, "/api/kc/tutor/answer", {
          sessionId, answer: pending.child_text, model, turnId: pending.turn_id, revision: pending.revision,
        });
        if (!response.ok) throw new Error((await response.text()) || "The tutor could not answer.");
        saved = await response.json();
      }
      const before = pending.session_before;
      const count = Number(before.message_count);
      const boundaryMatches = count === 0 || (Number.isInteger(count) && count > 0 && before.last_message_id
        && saved.messages[count - 1]?.id === before.last_message_id);
      // A current session GET can already include a replayed reply. Compare to the persisted pre-submit boundary.
      const messageId = boundaryMatches ? newTutorMessageId([], saved.messages.slice(count)) : null;
      return committedSnap(sessionId, saved, "answer", messageId);
    },
    answerKey: io?.answerKey ?? ((chatId) => api(`/kc/harness/chats/${chatId}/answer-key`)),
    childText: async (input) => {
      const response = await callRoute(routes.child, "/api/kc/harness/child", { ...input, needsModel: true });
      if (!response.ok) throw new Error((await response.text()) || "The child model failed.");
      return response.json();
    },
    recordTurn: async (chatId, body) => {
      const response = await callRoute(routes.turn, "/api/kc/harness/turn", { chatId, turn: body });
      if (!response.ok) throw new ApiError((await response.text()) || "Could not store the turn.", response.status);
      return response.json();
    },
    finish: async (chatId, reason, generation) => {
      const response = await callRoute(routes.finish, "/api/kc/harness/finish", { chatId, reason, claim_generation: generation });
      if (!response.ok) throw new Error((await response.text()) || "Could not finish the chat.");
    },
  };
}
