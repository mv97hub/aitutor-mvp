/** Mirrors the API paste count used to override a depth band. */

export const PASTE_LIMIT = 100_000;

export const PASTE_OVERRIDE_NOTE =
  "A longer paste overrides Standard depth. The course uses one component for each pasted unit or statement.";

const DEPTH_HIGH: Record<string, number> = {
  intro: 6,
  standard: 12,
  deep: 25,
  curriculum: 100,
};

const UNIT_HEADER = /^(?:unit|chapter|module)\s+\d+\s*[:.\-–—]\s*/i;
const BULLET = /^(?:[-*•]|\d+[.)])\s+/;

function countPaste(text: string, syllabusOnly: boolean): number {
  let units = 0;
  let statements = 0;
  for (const raw of String(text || "").split(/\r?\n/)) {
    const line = raw.trim().replace(BULLET, "");
    if (!line) continue;
    if (UNIT_HEADER.test(line)) {
      units += 1;
      continue;
    }
    statements += 1;
  }
  if (syllabusOnly && units === 0) return 0;
  if (units) return Math.max(units, statements);
  return statements;
}

/** The larger of standard statements and a syllabus in the source text. */
export function pastedCurriculumCount(standardText: string, sourceText: string): number {
  return Math.max(countPaste(standardText, false), countPaste(sourceText, true));
}

export function pasteOverridesDepth(depth: string, count: number): boolean {
  return count > (DEPTH_HIGH[depth] ?? DEPTH_HIGH.standard);
}

export function intakeCutNotes(intake: { source_text_cut?: boolean; standard_text_cut?: boolean }): string[] {
  const notes: string[] = [];
  if (intake.source_text_cut) notes.push(`Source text was cut at ${PASTE_LIMIT.toLocaleString("en-US")} characters.`);
  if (intake.standard_text_cut) notes.push(`Standard statements were cut at ${PASTE_LIMIT.toLocaleString("en-US")} characters.`);
  return notes;
}
