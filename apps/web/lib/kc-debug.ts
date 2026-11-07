export type KcDebugTurn = {
  id: string;
  seq: number;
  model: string;
  created_at: string;
  system_prompt: string;
  messages: unknown[];
  response: string;
  rubric_met?: string[];
  misconception?: string | null;
};

type StoredPrompt = {
  id: string;
  seq: number;
  message_id: string | null;
  system_prompt: string;
  messages: unknown[];
  model: string;
  rubric_met?: string[];
  misconception?: string | null;
  created_at: string;
};

/** Oldest call first, so the newest turn sits at the bottom of the log. */
export function debugTurns(detail: {
  messages: { id: string; content: string }[];
  prompts: StoredPrompt[];
}): KcDebugTurn[] {
  const byId = new Map(detail.messages.map((message) => [message.id, message.content]));
  return [...detail.prompts]
    .sort((left, right) => left.seq - right.seq)
    .map((prompt) => ({
      id: prompt.id,
      seq: prompt.seq,
      model: prompt.model,
      created_at: prompt.created_at,
      system_prompt: prompt.system_prompt,
      messages: Array.isArray(prompt.messages) ? prompt.messages : [],
      response: prompt.message_id ? (byId.get(prompt.message_id) ?? "") : "",
      rubric_met: prompt.rubric_met,
      misconception: prompt.misconception,
    }));
}
