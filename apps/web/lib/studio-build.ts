export type TemplateKind = "periods" | "units" | "framework";

export type BuildOperation = {
  op: "add";
  kind: "unit" | "quest";
  code: string;
  parent: string;
  title: string;
  position: null;
};

export type TemplateProposal = {
  phase: "structure";
  operations: BuildOperation[];
};

type PendingMessage = {
  applied: boolean;
  proposal: { operations: unknown[]; phase?: string } | null;
};

function add(kind: "unit" | "quest", code: string, parent: string, title: string): BuildOperation {
  return { op: "add", kind, code, parent, title, position: null };
}

function freeUnitNumbers(courseCode: string, taken: string[], count: number): number[] {
  const used = new Set<number>();
  for (const code of taken) {
    const match = new RegExp(`^${courseCode}-U(\\d+)$`).exec(code);
    if (match) used.add(Number(match[1]));
  }
  const numbers: number[] = [];
  for (let number = 1; numbers.length < count; number += 1) {
    if (!used.has(number)) numbers.push(number);
  }
  return numbers;
}

export function structureTemplate(
  courseCode: string,
  kind: TemplateKind,
  framework: string,
  taken: string[] = [],
): { content: string; proposal: TemplateProposal } {
  const code = courseCode.trim().toUpperCase();
  const count = kind === "units" ? 2 : 3;
  const [first, second, third] = freeUnitNumbers(code, taken.map((item) => item.toUpperCase()), count);
  if (kind === "periods") {
    return {
      content: "Three periods. Nothing is saved until you accept.",
      proposal: {
        phase: "structure",
        operations: [
          add("unit", `${code}-U${first}`, code, "Opening period"),
          add("unit", `${code}-U${second}`, code, "Middle period"),
          add("unit", `${code}-U${third}`, code, "Later period"),
        ],
      },
    };
  }
  if (kind === "units") {
    const left = `${code}-U${first}`;
    const right = `${code}-U${second}`;
    return {
      content: "Two units, with two quests each. Nothing is saved until you accept.",
      proposal: {
        phase: "structure",
        operations: [
          add("unit", left, code, "First unit"),
          add("quest", `${left}-Q1`, left, "First quest"),
          add("quest", `${left}-Q2`, left, "Second quest"),
          add("unit", right, code, "Second unit"),
          add("quest", `${right}-Q1`, right, "First quest"),
          add("quest", `${right}-Q2`, right, "Second quest"),
        ],
      },
    };
  }
  const name = framework.trim() || "a widely known framework";
  return {
    content: `A short outline suggested from ${name}. This is a suggestion. Nothing is saved until you accept.`,
    proposal: {
      phase: "structure",
      operations: [
        add("unit", `${code}-U${first}`, code, `${name}: opening`),
        add("unit", `${code}-U${second}`, code, `${name}: middle`),
        add("unit", `${code}-U${third}`, code, `${name}: close`),
      ],
    },
  };
}

export function bulkPrompt(phase: "goals" | "close", codes: string[]): string {
  const listed = codes.join(", ");
  if (phase === "goals") {
    return `Offer a learning goal for each open quest, addressed by that quest's code. Codes still open in this phase: ${listed}. Do not fill close style in this patch.`;
  }
  return `Offer quest-close choices for each open quest, addressed by that quest's code. Codes still open in this phase: ${listed}.`;
}

export function pendingInPhase<T extends PendingMessage>(messages: T[], phase: string): T[] {
  return messages.filter((message) => {
    if (message.applied || !message.proposal || message.proposal.operations.length === 0) return false;
    return !message.proposal.phase || message.proposal.phase === phase;
  });
}
