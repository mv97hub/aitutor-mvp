export type SentPrompt = {
  label: string;
  instructions: string;
  prompt: string;
};

export type PromptTurn = {
  id: string;
  prompts: SentPrompt[];
};

export class KcDraftError extends Error {
  readonly prompts: SentPrompt[];
  readonly promptTurnId: string;

  constructor(message: string, prompts: SentPrompt[], promptTurnId = "") {
    super(message);
    this.name = "KcDraftError";
    this.prompts = prompts;
    this.promptTurnId = promptTurnId;
  }
}

/** One in-flight call per key. The entry is dropped when the call settles. */
export function shareInFlight<T>(bucket: Map<string, Promise<T>>, key: string, run: () => Promise<T>): Promise<T> {
  const existing = bucket.get(key);
  if (existing) return existing;
  const promise = Promise.resolve()
    .then(run)
    .finally(() => {
      if (bucket.get(key) === promise) bucket.delete(key);
    });
  bucket.set(key, promise);
  return promise;
}

export function releaseRecord(record: Record<string, unknown>) {
  for (const key of Object.keys(record)) delete record[key];
}

/** Keep the component rows and drop the rest of that slice's model output. */
export function takeComponentRows(proposal: Record<string, unknown>): Record<string, unknown>[] {
  const raw = proposal.components;
  delete proposal.components;
  if (!Array.isArray(raw)) {
    releaseRecord(proposal);
    return [];
  }
  const rows: Record<string, unknown>[] = [];
  for (let index = 0; index < raw.length; index += 1) {
    const item = raw[index];
    raw[index] = undefined;
    if (item && typeof item === "object") rows.push(item as Record<string, unknown>);
  }
  raw.length = 0;
  releaseRecord(proposal);
  return rows;
}

export function promptTurnId(parts: readonly string[]): string {
  let hash = 2166136261;
  for (const part of parts) {
    for (let index = 0; index < part.length; index += 1) {
      hash ^= part.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    hash ^= 0xff;
    hash >>>= 0;
  }
  return hash.toString(16);
}

export const CREATOR_PROMPT_TOPIC_CAP = 8;
export const CREATOR_PROMPT_PASS_CAP = 64;

const handoff = new Map<string, PromptTurn>();

function copyPrompt(item: SentPrompt): SentPrompt {
  return { label: item.label, instructions: item.instructions, prompt: item.prompt };
}

function copyTurn(turn: PromptTurn): PromptTurn {
  return {
    id: turn.id,
    prompts: turn.prompts.slice(0, CREATOR_PROMPT_PASS_CAP).map(copyPrompt),
  };
}

/** Latest turn for a topic, capped so the server does not keep a prompt log. */
export function rememberCreatorPrompts(topicId: string, turn: PromptTurn) {
  const id = topicId.trim();
  if (!id || turn.prompts.length === 0 || !turn.id) return;
  handoff.delete(id);
  handoff.set(id, copyTurn(turn));
  while (handoff.size > CREATOR_PROMPT_TOPIC_CAP) {
    const oldest = handoff.keys().next().value;
    if (oldest === undefined) break;
    handoff.delete(oldest);
  }
}

export function readCreatorPrompts(topicId: string): PromptTurn | null {
  const turn = handoff.get(topicId.trim());
  return turn ? copyTurn(turn) : null;
}

export function resetCreatorPromptHandoff() {
  handoff.clear();
}

const STORAGE_PREFIX = "kc-draft-prompts:";

export type PromptStore = {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
};

function isSentPrompt(value: unknown): value is SentPrompt {
  if (!value || typeof value !== "object") return false;
  const item = value as SentPrompt;
  return typeof item.label === "string" && typeof item.instructions === "string" && typeof item.prompt === "string";
}

function readTurns(store: PromptStore | null, key: string): PromptTurn[] {
  if (!store) return [];
  const raw = store.getItem(key);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is PromptTurn => {
      if (!item || typeof item !== "object") return false;
      const turn = item as PromptTurn;
      return typeof turn.id === "string" && Array.isArray(turn.prompts) && turn.prompts.every(isSentPrompt);
    }).map(copyTurn);
  } catch {
    return [];
  }
}

function writeTurns(store: PromptStore, key: string, turns: PromptTurn[]): PromptTurn[] {
  let next = turns;
  while (next.length > 0) {
    try {
      store.setItem(key, JSON.stringify(next));
      return next;
    } catch {
      if (next.length === 1) {
        try {
          store.removeItem(key);
        } catch {
          /* The panel can still show this turn for the current view. */
        }
        return next;
      }
      next = next.slice(1);
    }
  }
  return [];
}

/** Append one turn for this course or topic. A repeat of the same id stays put. Newest last. */
export function mergePromptTurns(scope: string, incoming: PromptTurn | null, store: PromptStore | null): PromptTurn[] {
  if (!scope) return [];
  const key = `${STORAGE_PREFIX}${scope}`;
  const history = readTurns(store, key);
  if (!incoming || incoming.prompts.length === 0 || !incoming.id) return history;
  if (history.some((item) => item.id === incoming.id)) return history;
  const next = [...history, copyTurn(incoming)];
  if (!store) return next;
  return writeTurns(store, key, next);
}
