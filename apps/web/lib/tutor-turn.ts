/** The decision is already stored. A later log failure still returns that session. */

export async function finishSavedTurn<T>(session: T, log: () => Promise<void>): Promise<T> {
  try {
    await log();
  } catch {
    // The child is not asked to send the turn again.
  }
  return session;
}
