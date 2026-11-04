export function bulkPrompt(phase: "goals" | "close", codes: string[]): string {
  const listed = codes.join(", ");
  if (phase === "goals") {
    return `Offer a learning goal for each open quest, addressed by that quest's code. A quest can hold several goals, and each goal needs its own success criterion. Draft a criterion whenever you draft a goal. Codes still open in this phase: ${listed}. Do not fill close style in this patch.`;
  }
  return `Offer quest-close choices for each open quest, addressed by that quest's code. Codes still open in this phase: ${listed}.`;
}
