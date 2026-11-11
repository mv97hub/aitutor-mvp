/** Buttons under the explanation that opens a topic or goal. Clicks send these labels. */

export const TELL_ME_MORE_LABEL = "Tell me more";
export const MOVE_ON_LABEL = "Got it - move on";

export function goalStartActions(input: {
  status: string;
  needsSpeech: boolean;
  blockType?: string;
  substep?: string;
  choosing?: boolean;
}): string[] {
  if (input.choosing || input.needsSpeech || input.status === "completed") return [];
  if (input.blockType !== "topic_goal" || input.substep !== "explain") return [];
  return [TELL_ME_MORE_LABEL, MOVE_ON_LABEL];
}
