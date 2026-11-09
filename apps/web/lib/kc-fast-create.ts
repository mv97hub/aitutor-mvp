/**
 * Fast Create All walks the selected course's empty components.
 * An empty component has no blocks, or only the course's default topic and goal
 * blocks. A core truth, another block type, or a filled acceptance criterion or
 * teaching note means the component is already started. The cycle selects one,
 * sends Create Draft, pushes the reply, then marks it complete when the gaps are empty.
 */

export const CREATE_DRAFT_MESSAGE = "Create Draft";

export type FastPhase = "draft" | "draft-sent" | "push-sent" | "complete-sent";

export type FastRecord = {
  active: boolean;
  courseId: string;
  ids: string[];
  index: number;
  done: number;
  phase: FastPhase;
  model: string;
  baseline: number;
  gapId: string | null;
  token: number;
};

export type FastView = {
  courseId: string | null;
  componentId: string | null;
  messageCount: number;
  hasDraft: boolean;
  missing: string[];
  markedComplete: boolean;
  error: string | null;
};

export type FastAction =
  | { type: "none" }
  | { type: "open"; courseId: string; componentId: string; model: string }
  | { type: "draft"; model: string }
  | { type: "push" }
  | { type: "complete" };

const PHASES: readonly FastPhase[] = ["draft", "draft-sent", "push-sent", "complete-sent"];

type FastComponent = {
  id: string;
  blocks?: unknown[] | null;
  topics?: { topic?: unknown; goal?: unknown }[] | null;
  core_truth?: string | null;
};

function filledText(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (value == null) return "";
  return String(value).trim();
}

function pairKey(topic: string, goal: string): string {
  return `${topic}\n${goal}`;
}

function storedPairKeys(topics: FastComponent["topics"]): Set<string> {
  const keys = new Set<string>();
  if (!Array.isArray(topics)) return keys;
  for (const item of topics) {
    if (!item || typeof item !== "object") continue;
    const topic = filledText(item.topic);
    const goal = filledText(item.goal);
    if (topic && goal) keys.add(pairKey(topic, goal));
  }
  return keys;
}

function isBlankCatalogValue(value: unknown): boolean {
  if (value == null) return true;
  if (typeof value === "string") return value.trim() === "";
  if (Array.isArray(value)) return value.every(isBlankCatalogValue);
  return false;
}

/** A course push stores each topic and goal on a topic_goal block and leaves the other catalog fields empty. */
function isDefaultTopicBlock(block: unknown, pairs: Set<string>): boolean {
  if (!block || typeof block !== "object") return false;
  const record = block as { type?: unknown; data?: unknown };
  if (record.type !== "topic_goal") return false;
  const data = record.data && typeof record.data === "object" ? (record.data as Record<string, unknown>) : {};
  const topic = filledText(data.topic);
  const goal = filledText(data.goal);
  if (!pairs.has(pairKey(topic, goal))) return false;
  return isBlankCatalogValue(data.acceptance_criteria) && isBlankCatalogValue(data.teaching_notes);
}

export function emptyComponentIds(components: FastComponent[]): string[] {
  return components
    .filter((item) => {
      if (filledText(item.core_truth)) return false;
      const blocks = item.blocks;
      if (!Array.isArray(blocks) || blocks.length === 0) return true;
      const pairs = storedPairKeys(item.topics);
      return blocks.every((block) => isDefaultTopicBlock(block, pairs));
    })
    .map((item) => item.id);
}

/** Same gap line the structure row shows: the missing strings, joined. */
export function gapLabel(missing: string[]): string {
  return missing.join(", ");
}

export function fastProgress(record: FastRecord | null): { done: number; total: number } | null {
  if (!record) return null;
  return { done: record.done, total: record.ids.length };
}

export function creatorHref(courseId: string, componentId: string, model: string): string {
  const params = new URLSearchParams();
  params.set("course", courseId);
  params.set("kc", componentId);
  if (model) params.set("model", model);
  return `/kc-creator?${params.toString()}`;
}

export function beginFastCreate(courseId: string, ids: string[], model: string, token = Date.now()): FastRecord {
  return {
    active: ids.length > 0,
    courseId,
    ids,
    index: 0,
    done: 0,
    phase: "draft",
    model,
    baseline: 0,
    gapId: null,
    token,
  };
}

function stop(record: FastRecord, gapId: string | null = null): { record: FastRecord; action: FastAction } {
  if (!record.active && record.gapId === gapId) return { record, action: { type: "none" } };
  return { record: { ...record, active: false, gapId }, action: { type: "none" } };
}

function open(record: FastRecord, componentId: string): { record: FastRecord; action: FastAction } {
  return {
    record,
    action: { type: "open", courseId: record.courseId, componentId, model: record.model },
  };
}

/**
 * One step of the cycle. The caller performs the action, then keeps the
 * returned record. A second call with the same view does not repeat the action.
 */
export function stepFastCreate(record: FastRecord, view: FastView): { record: FastRecord; action: FastAction } {
  if (!record.active) return { record, action: { type: "none" } };
  const current = record.ids[record.index];
  if (!current) return stop(record);

  const onCurrent = view.courseId === record.courseId && view.componentId === current;
  if (view.error && record.phase !== "draft") return stop(record);

  if (!onCurrent) {
    if (record.phase !== "draft") return { record, action: { type: "none" } };
    return open(record, current);
  }

  if (record.phase === "draft") {
    if (view.error) return open(record, current);
    return {
      record: { ...record, phase: "draft-sent", baseline: view.messageCount },
      action: { type: "draft", model: record.model },
    };
  }

  if (record.phase === "draft-sent") {
    if (view.messageCount > record.baseline && view.hasDraft) {
      return { record: { ...record, phase: "push-sent" }, action: { type: "push" } };
    }
    if (view.messageCount > record.baseline && !view.hasDraft) return stop(record);
    return { record, action: { type: "none" } };
  }

  if (record.phase === "push-sent") {
    if (view.hasDraft) return { record, action: { type: "none" } };
    if (view.missing.length > 0) return stop(record, current);
    return { record: { ...record, phase: "complete-sent" }, action: { type: "complete" } };
  }

  if (!view.markedComplete) return { record, action: { type: "none" } };
  const done = record.done + 1;
  const index = record.index + 1;
  const nextId = record.ids[index];
  if (!nextId) {
    return {
      record: { ...record, active: false, done, index, phase: "draft", baseline: 0, gapId: null },
      action: { type: "none" },
    };
  }
  return {
    record: { ...record, done, index, phase: "draft", baseline: 0, gapId: null },
    action: { type: "open", courseId: record.courseId, componentId: nextId, model: record.model },
  };
}

const STORAGE_KEY = "kc-fast-create";

function isRecord(value: unknown): value is FastRecord {
  if (!value || typeof value !== "object") return false;
  const record = value as FastRecord;
  return (
    typeof record.active === "boolean" &&
    typeof record.courseId === "string" &&
    Array.isArray(record.ids) &&
    record.ids.every((id) => typeof id === "string") &&
    typeof record.index === "number" &&
    typeof record.done === "number" &&
    PHASES.includes(record.phase) &&
    typeof record.model === "string" &&
    typeof record.baseline === "number" &&
    (record.gapId === null || typeof record.gapId === "string") &&
    typeof record.token === "number"
  );
}

export function readFastCreate(): FastRecord | null {
  if (typeof sessionStorage === "undefined") return null;
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    return isRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function writeFastCreate(record: FastRecord | null): void {
  if (typeof sessionStorage === "undefined") return;
  if (!record) sessionStorage.removeItem(STORAGE_KEY);
  else sessionStorage.setItem(STORAGE_KEY, JSON.stringify(record));
}
