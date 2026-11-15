/** The server loop calls the same tutor routes the page calls. One route, one model call. */

import { api } from "./api.ts";
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
  session: (sessionId: string) => Promise<SessionSnap>;
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

export async function readSnap(sessionId: string): Promise<SessionSnap> {
  const session = await api<SessionSnap>(`/kc/tutor/sessions/${sessionId}`);
  let prompt = "";
  let safety = "none";
  let loop: SessionSnap["loop_result"] = session.loop_result ?? null;
  let loopDecision = session.loop_decision || "";
  try {
    const detail = await api<{
      prompts?: {
        system_prompt?: string;
        decision?: {
          safety_flag?: string;
          loop_result?: SessionSnap["loop_result"];
          loop_decision?: string;
        };
      }[];
    }>(`/kc/sessions/${sessionId}`);
    const latest = detail.prompts?.[detail.prompts.length - 1];
    prompt = latest?.system_prompt || "";
    safety = latest?.decision?.safety_flag || "none";
    if (latest?.decision?.loop_result) loop = latest.decision.loop_result;
    if (latest?.decision?.loop_decision) loopDecision = latest.decision.loop_decision;
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
  return {
    runStatus: io?.runStatus ?? (() => api<RunStatus>(`/kc/harness/runs/${runId}`)),
    session,
    speak: async (sessionId, model) => {
      const response = await callRoute(routes.speak, "/api/kc/tutor/speak", { sessionId, model });
      if (!response.ok) throw new Error((await response.text()) || "The tutor could not speak.");
      return session(sessionId);
    },
    answer: async (sessionId, text, model) => {
      const response = await callRoute(routes.answer, "/api/kc/tutor/answer", { sessionId, answer: text, model });
      if (!response.ok) throw new Error((await response.text()) || "The tutor could not answer.");
      return session(sessionId);
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
