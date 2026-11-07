/** The model call stored for View chats. KC Tutor uses the same shape. */

export type ModelCall = {
  prompt?: Array<{ role?: string; content?: unknown }>;
  temperature?: number;
  maxOutputTokens?: number;
  topP?: number;
  topK?: number;
  presencePenalty?: number;
  frequencyPenalty?: number;
  stopSequences?: string[];
  seed?: number;
  responseFormat?: unknown;
  tools?: unknown;
  toolChoice?: unknown;
  reasoning?: string;
};

function jsonSafe(value: unknown): unknown {
  return JSON.parse(
    JSON.stringify(value, (_key, item: unknown) => {
      if (typeof item === "bigint") return item.toString();
      if (item instanceof Uint8Array) return Buffer.from(item).toString("base64");
      return item;
    }),
  );
}

function textOfContent(content: unknown) {
  return typeof content === "string" ? content : JSON.stringify(content);
}

export function requestForCall(params: ModelCall, fallbackSystem: string) {
  const prompt = Array.isArray(params.prompt) ? params.prompt : [];
  const systemParts = prompt
    .filter((message) => message.role === "system")
    .map((message) => textOfContent(message.content))
    .filter((text) => text.length > 0);
  let systemPrompt = systemParts.join("\n\n");
  if (fallbackSystem && !systemPrompt.includes(fallbackSystem)) {
    systemPrompt = systemPrompt ? `${fallbackSystem}\n\n${systemPrompt}` : fallbackSystem;
  }
  const messages = prompt.filter((message) => message.role !== "system");
  const extras: Record<string, unknown> = {};
  if (params.temperature != null) extras.temperature = params.temperature;
  if (params.maxOutputTokens != null) extras.maxOutputTokens = params.maxOutputTokens;
  if (params.topP != null) extras.topP = params.topP;
  if (params.topK != null) extras.topK = params.topK;
  if (params.presencePenalty != null) extras.presencePenalty = params.presencePenalty;
  if (params.frequencyPenalty != null) extras.frequencyPenalty = params.frequencyPenalty;
  if (params.stopSequences != null) extras.stopSequences = params.stopSequences;
  if (params.seed != null) extras.seed = params.seed;
  if (params.responseFormat != null) extras.responseFormat = params.responseFormat;
  if (params.tools != null) extras.tools = params.tools;
  if (params.toolChoice != null) extras.toolChoice = params.toolChoice;
  if (params.reasoning != null && params.reasoning !== "provider-default") extras.reasoning = params.reasoning;
  const storedMessages = Object.keys(extras).length > 0 ? [...messages, { role: "request", content: extras }] : messages;
  return {
    system_prompt: systemPrompt || fallbackSystem,
    messages: jsonSafe(storedMessages),
  };
}
