import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  CREATOR_PROMPT_PASS_CAP,
  CREATOR_PROMPT_TOPIC_CAP,
  mergePromptTurns,
  promptTurnId,
  readCreatorPrompts,
  releaseRecord,
  rememberCreatorPrompts,
  resetCreatorPromptHandoff,
  type PromptStore,
  type PromptTurn,
  type SentPrompt,
} from "./kc-prompt-log.ts";

function memoryStore(seed: Record<string, string> = {}): PromptStore & { data: Record<string, string> } {
  const data = { ...seed };
  return {
    data,
    getItem(key) {
      return Object.prototype.hasOwnProperty.call(data, key) ? data[key] : null;
    },
    setItem(key, value) {
      data[key] = value;
    },
    removeItem(key) {
      delete data[key];
    },
  };
}

function turn(id: string, instructions: string, prompt = "user"): PromptTurn {
  return { id, prompts: [{ label: "Draft", instructions, prompt }] };
}

test("releaseRecord drops every field on the model object", () => {
  const record: Record<string, unknown> = { subject: "Geometry", titles: ["Angles"], raw: "output" };
  releaseRecord(record);
  assert.deepEqual(record, {});
});

test("topic handoff keeps only the latest turn and a small set of topics", () => {
  resetCreatorPromptHandoff();
  rememberCreatorPrompts("topic-a", turn("old", "first instructions"));
  rememberCreatorPrompts("topic-a", turn("new", "second instructions"));
  assert.equal(readCreatorPrompts("topic-a")?.id, "new");
  assert.equal(readCreatorPrompts("topic-a")?.prompts[0]?.instructions, "second instructions");
  assert.equal(readCreatorPrompts("topic-a")?.prompts.length, 1);

  for (let index = 0; index < CREATOR_PROMPT_TOPIC_CAP + 1; index += 1) {
    rememberCreatorPrompts(`topic-${index}`, turn(`id-${index}`, `instructions ${index}`));
  }
  assert.equal(readCreatorPrompts("topic-0"), null);
  assert.equal(readCreatorPrompts(`topic-${CREATOR_PROMPT_TOPIC_CAP}`)?.id, `id-${CREATOR_PROMPT_TOPIC_CAP}`);
  assert.equal(readCreatorPrompts("missing"), null);

  const long = Array.from({ length: CREATOR_PROMPT_PASS_CAP + 3 }, (_, index) => ({
    label: `Slice ${index + 1}`,
    instructions: `i${index}`,
    prompt: `p${index}`,
  }));
  rememberCreatorPrompts("topic-long", { id: "long", prompts: long });
  assert.equal(readCreatorPrompts("topic-long")?.prompts.length, CREATOR_PROMPT_PASS_CAP);
  assert.equal(readCreatorPrompts("topic-long")?.prompts[0]?.label, "Slice 1");

  const extra = {
    label: "Title pass",
    instructions: "system",
    prompt: "user",
    model: "gpt",
    temperature: 0.3,
  } as SentPrompt;
  rememberCreatorPrompts("topic", { id: "t", prompts: [extra] });
  assert.deepEqual(readCreatorPrompts("topic")?.prompts[0], {
    label: "Title pass",
    instructions: "system",
    prompt: "user",
  });
  resetCreatorPromptHandoff();
});

test("browser history appends a turn and keeps the newest last", () => {
  const store = memoryStore();
  const first = turn("a", "title pass");
  const second = turn("b", "slice");
  assert.deepEqual(
    mergePromptTurns("course:1", first, store).map((item) => item.id),
    ["a"],
  );
  const history = mergePromptTurns("course:1", second, store);
  assert.deepEqual(
    history.map((item) => item.id),
    ["a", "b"],
  );
  assert.deepEqual(
    mergePromptTurns("course:1", second, store).map((item) => item.id),
    ["a", "b"],
  );
  assert.deepEqual(mergePromptTurns("course:2", null, store), []);
  assert.deepEqual(mergePromptTurns("", first, store), []);

  const stored = JSON.parse(store.data["kc-draft-prompts:course:1"] ?? "[]") as PromptTurn[];
  assert.equal(stored[1]?.prompts[0]?.instructions, "slice");
  assert.equal(Object.keys(stored[1]?.prompts[0] ?? {}).join(","), "label,instructions,prompt");
});

test("prompt turn ids are stable for the same text", () => {
  const parts = ["course", "explain angles", "Blueprint", "system", "user"];
  assert.equal(promptTurnId(parts), promptTurnId(parts));
  assert.notEqual(promptTurnId(parts), promptTurnId([...parts, "again"]));
});

test("draft calls record prompt text without keeping a finished draft", () => {
  const source = readFileSync(new URL("./kc-draft.ts", import.meta.url), "utf8");
  assert.match(source, /sent\.push\(\{ label, instructions, prompt \}\)/);
  assert.doesNotMatch(source, /cache\.set|const cache/);

  const panel = readFileSync(new URL("../components/CreatorDebug.tsx", import.meta.url), "utf8");
  assert.match(panel, /item\.instructions/);
  assert.match(panel, /item\.prompt/);
  assert.doesNotMatch(panel, /temperature|schema|turn\.model/);
});
