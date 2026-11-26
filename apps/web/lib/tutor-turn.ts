/** The decision is already stored. A later log failure still returns that session. */

export async function finishSavedTurn<T>(session: T, log: () => Promise<void>): Promise<T> {
  try {
    await log();
  } catch {
    // The child is not asked to send the turn again.
  }
  return session;
}


type Message = { id?: string; role: string };

/** Only a new, uniquely identified assistant message may own this call's logs. */
export function newTutorMessageId(before: Message[], after: Message[]): string | null {
  if (before.some((message, i) => !message.id || message.id !== after[i]?.id)) return null;
  const added = after.slice(before.length).filter((message) => message.role === "assistant");
  return added.length === 1 && added[0] === after[after.length - 1] ? added[0].id || null : null;
}
