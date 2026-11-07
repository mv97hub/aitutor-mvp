export type LinkedPrompt = {
  id: string;
  message_id: string | null;
  seq: number;
};

/** Place each stored model call on the transcript row that should show it. */
export function promptsOnTranscript<T extends LinkedPrompt>(
  messages: { id: string; role: string }[],
  prompts: T[],
): { placed: Map<string, T>; leftover: T[] } {
  const ids = new Set(messages.map((message) => message.id));
  const byMessage = new Map<string, T>();
  const unlinked: T[] = [];
  for (const prompt of [...prompts].sort((left, right) => left.seq - right.seq)) {
    if (prompt.message_id && ids.has(prompt.message_id)) {
      byMessage.set(prompt.message_id, prompt);
    } else {
      unlinked.push(prompt);
    }
  }

  const placed = new Map<string, T>();
  const used = new Set<string>();
  messages.forEach((message, index) => {
    const prompt = byMessage.get(message.id);
    if (!prompt || used.has(prompt.id)) return;
    let target = message.id;
    if (message.role === "user") {
      const next = messages[index + 1];
      if (next && next.role === "assistant") target = next.id;
    }
    if (placed.has(target)) {
      if (target !== message.id && !placed.has(message.id)) {
        placed.set(message.id, prompt);
        used.add(prompt.id);
      }
      return;
    }
    placed.set(target, prompt);
    used.add(prompt.id);
  });

  const leftover: T[] = [];
  for (const prompt of byMessage.values()) {
    if (!used.has(prompt.id)) leftover.push(prompt);
  }
  for (const prompt of unlinked) {
    const open = messages.find((message) => message.role === "assistant" && !placed.has(message.id));
    if (!open) {
      leftover.push(prompt);
      continue;
    }
    placed.set(open.id, prompt);
  }
  leftover.sort((left, right) => left.seq - right.seq);
  return { placed, leftover };
}
