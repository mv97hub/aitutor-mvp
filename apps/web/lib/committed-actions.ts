/** Buttons the committed session already chose. Absent means the screen keeps its own. */

export function committedButtons(actions: string[] | null | undefined): string[] | null {
  return Array.isArray(actions) ? actions : null;
}
