/** Start and end marks for a stored harness transcript. */

export type MarkTurn = {
  seq: number;
  session_after?: {
    block_id?: string;
    block_type?: string;
    block_title?: string;
  };
};

export type BlockMark = { seq: number; edge: "start" | "end"; label: string };

const BLOCK_LABELS: Record<string, string> = {
  topic_goal: "Topic / Goal",
  mcq: "Multiple Choice Question",
  case_study: "Case Study / Contrasting Cases",
  socratic: "Socratic Discussion",
  curiosity: "Curiosity / Wonder Hook",
  worked_example: "Worked Example + Faded Step",
  spot_the_flaw: "Spot the Flaw / Buggy Rule",
  teach_back: "Teach-Back / Feynman",
  retrieval_check: "Retrieval & Elaborative Interrogation",
  explanation: "Explanatory Walkthrough",
  passage_ela: "ELA Reading Passage",
};

export function blockTypeLabel(value: string): string {
  const key = value.trim();
  if (!key) return "";
  return BLOCK_LABELS[key] || key.replaceAll("_", " ");
}

function blockKey(turn: MarkTurn): string {
  const after = turn.session_after || {};
  const id = String(after.block_id || "").trim();
  if (id) return `id:${id}`;
  const type = String(after.block_type || "").trim();
  if (type) return `type:${type}`;
  return "";
}

export function blockMarkLabel(turn: MarkTurn): string {
  const after = turn.session_after || {};
  const type = blockTypeLabel(String(after.block_type || ""));
  const title = String(after.block_title || "").trim();
  if (type && title) return `${type} — ${title}`;
  return type || "Block";
}

/** Mark the first turn of a block and the last turn before the next block. */
export function blockMarks(turns: MarkTurn[]): BlockMark[] {
  const marks: BlockMark[] = [];
  let previous = "";
  turns.forEach((turn, index) => {
    const key = blockKey(turn);
    if (!key) return;
    const next = turns[index + 1];
    const nextKey = next ? blockKey(next) : "";
    if (key !== previous) {
      marks.push({ seq: turn.seq, edge: "start", label: blockMarkLabel(turn) });
    }
    if (next && nextKey && nextKey !== key) {
      marks.push({ seq: turn.seq, edge: "end", label: blockMarkLabel(turn) });
    }
    previous = key;
  });
  return marks;
}
