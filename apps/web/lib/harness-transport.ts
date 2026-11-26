/** The server loop calls the same tutor routes the page calls. One route, one model call. */

import { api } from "./api.ts";
import { newTutorMessageId } from "./tutor-turn.ts";
import type { HarnessTransport, RunStatus, SessionSnap } from "./harness-runner.ts";

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
  let safety = "none";
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
    safety = record?.decision?.safety_flag || "none";
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
  async function committedSnap(prior: SessionSnap, response: Response, kind: "speak" | "answer") {
    const saved: SessionSnap = await response.json();
    const messageId = newTutorMessageId(prior.messages, saved.messages);
    return {
      ...await session(prior.id, saved),
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
      return committedSnap(prior, response, "speak");
    },
    answer: async (sessionId, text, model) => {
      const prior = await session(sessionId);
      const response = await callRoute(routes.answer, "/api/kc/tutor/answer", {
        sessionId,
        answer: text,
        model,
        turnId: crypto.randomUUID(),
        revision: prior.revision ?? 0,
      });
      if (!response.ok) throw new Error((await response.text()) || "The tutor could not answer.");
      return committedSnap(prior, response, "answer");
    },
    answerKey: io?.answerKey ?? ((chatId) => api(`/kc/harness/chats/${chatId}/answer-key`)),
    childText: async (input) => {
      const response = await callRoute(routes.child, "/api/kc/harness/child", { ...input, needsModel: true });
      if (!response.ok) throw new Error((await response.text()) || "The child model failed.");
      return response.json();
    },
    recordTurn: async (chatId, body) => {
      const response = await callRoute(routes.turn, "/api/kc/harness/turn", { chatId, turn: body });
      if (!response.ok) throw new Error((await response.text()) || "Could not store the turn.");
      return response.json();
    },
    finish: async (chatId, reason) => {
      const response = await callRoute(routes.finish, "/api/kc/harness/finish", { chatId, reason });
      if (!response.ok) throw new Error((await response.text()) || "Could not finish the chat.");
    },
  };
}
