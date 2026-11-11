/** A JSON file of the KC session the View Chats page already loaded. No extra request. */

export type ChatDownloadMessage = {
  role: string;
  content: string;
  created_at: string;
  block_step?: string | null;
};

export type ChatDownloadPrompt = {
  system_prompt: string;
  messages: unknown[];
  model?: string;
  created_at: string;
  rubric_met?: string[];
  misconception?: string | null;
};

/** The session detail from GET /kc/sessions/{id}, plus fields that detail may already carry. */
export type ChatDownloadSession = {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  student: { display_name: string };
  course: unknown;
  component: unknown;
  tutor?: unknown;
  messages: ChatDownloadMessage[];
  prompts?: ChatDownloadPrompt[];
  safety_events?: unknown;
};

export type KcChatDownloadMessage = {
  role: string;
  text: string;
  time: string;
  block_step?: string;
};

export type KcChatDownloadPrompt = {
  system_prompt: string;
  messages: unknown[];
  model: string;
  time: string;
  rubric_met?: string[];
  misconception?: string;
};

export type KcChatDownload = {
  student: ChatDownloadSession["student"];
  course: unknown;
  component: unknown;
  tutor: unknown;
  session_id: string;
  status: string;
  started_at: string;
  updated_at: string;
  messages: KcChatDownloadMessage[];
  prompts: KcChatDownloadPrompt[];
  safety_events?: unknown;
};

function blockStep(message: ChatDownloadMessage): string | undefined {
  if (typeof message.block_step !== "string") return undefined;
  const step = message.block_step.trim();
  return step || undefined;
}

function promptRow(prompt: ChatDownloadPrompt): KcChatDownloadPrompt {
  const row: KcChatDownloadPrompt = {
    system_prompt: prompt.system_prompt,
    messages: prompt.messages,
    model: prompt.model ?? "",
    time: prompt.created_at,
  };
  if (prompt.rubric_met && prompt.rubric_met.length > 0) row.rubric_met = prompt.rubric_met;
  if (prompt.misconception) row.misconception = prompt.misconception;
  return row;
}

/** Pretty-printed chat file. Prompts are the stored calls the debug panel shows. */
export function kcChatDownload(session: ChatDownloadSession): KcChatDownload {
  const download: KcChatDownload = {
    student: session.student,
    course: session.course,
    component: session.component,
    tutor: Object.prototype.hasOwnProperty.call(session, "tutor") ? (session.tutor ?? null) : null,
    session_id: session.id,
    status: session.status,
    started_at: session.created_at,
    updated_at: session.updated_at,
    messages: session.messages.map((message) => {
      const row: KcChatDownloadMessage = {
        role: message.role,
        text: message.content,
        time: message.created_at,
      };
      const step = blockStep(message);
      if (step) row.block_step = step;
      return row;
    }),
    prompts: (session.prompts ?? []).map(promptRow),
  };
  if (Object.prototype.hasOwnProperty.call(session, "safety_events")) {
    download.safety_events = session.safety_events;
  }
  return download;
}

export function kcChatDownloadJson(session: ChatDownloadSession): string {
  return `${JSON.stringify(kcChatDownload(session), null, 2)}\n`;
}

/** kc-chat-{student}-{session id}.json */
export function kcChatDownloadFilename(session: ChatDownloadSession): string {
  const student = session.student.display_name
    .trim()
    .replace(/[\\/:*?"<>|\u0000-\u001f]+/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return `kc-chat-${student || "student"}-${session.id}.json`;
}

export function downloadKcChat(session: ChatDownloadSession): void {
  const blob = new Blob([kcChatDownloadJson(session)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = kcChatDownloadFilename(session);
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
