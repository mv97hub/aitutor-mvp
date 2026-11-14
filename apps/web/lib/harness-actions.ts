/**
 * What a test child can do on this turn.
 * The labels match the buttons in KcLesson. Typing stays off while a choice card is showing.
 */

import { TELL_ME_MORE_LABEL, MOVE_ON_LABEL, goalStartActions } from "./kc-goal-start.ts";
import { choiceShowing, lessonComposerVisible } from "./learn-mobile.ts";

export const CONTINUE_LABEL = "No final questions — let's continue!";

export const HARNESS_BUTTONS = [TELL_ME_MORE_LABEL, MOVE_ON_LABEL, CONTINUE_LABEL] as const;

export type HarnessChoice = { id: string; text: string; correct?: boolean };

export type HarnessSession = {
  status: string;
  needs_speech: boolean;
  active_block_type?: string;
  active_substep?: string;
  choice?: { prompt: string; choices: { id: string; text: string }[] } | null;
};

export function availableActions(session: HarnessSession): {
  canType: boolean;
  buttons: string[];
  choices: HarnessChoice[];
} {
  const choosing = choiceShowing({
    hasChoice: Boolean(session.choice && session.choice.choices.length > 0),
    status: session.status,
    needsSpeech: session.needs_speech,
    settled: false,
  });
  const buttons = [
    ...goalStartActions({
      status: session.status,
      needsSpeech: session.needs_speech,
      blockType: session.active_block_type,
      substep: session.active_substep,
      choosing,
    }),
  ];
  const composerOpen = session.status !== "completed" && !session.needs_speech;
  if (composerOpen && session.active_block_type === "explanation" && !choosing) {
    if (session.active_substep === "summary_check") buttons.push(CONTINUE_LABEL);
    else buttons.push(TELL_ME_MORE_LABEL, MOVE_ON_LABEL);
  }
  const canType = lessonComposerVisible({
    status: session.status,
    needsSpeech: session.needs_speech,
    choosing,
    hideWhileChoosing: true,
  });
  const choices = choosing
    ? (session.choice?.choices ?? []).map((choice) => ({ id: choice.id, text: choice.text }))
    : [];
  return { canType, buttons, choices };
}
