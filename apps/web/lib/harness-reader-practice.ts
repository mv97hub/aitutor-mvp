/** A bounded replay of the six-year-old's River roads practice exchange. */
export const READER_PRACTICE = "river-example-practice";
export const EXAMPLE_REQUEST = "Tell me more";
export const CARGO_ANSWER = "Pears!";

type Course = { id: string; code: string; ready: boolean; components: { id: string; code: string }[] };

export function readerPracticePlan(courses: Course[], children: { id: string; number: number }[]) {
  const course = courses.find(row => row.ready && row.code === "harness-profile-scenarios");
  const river = course?.components.find(row => row.code === "harness-scenario-river");
  const child = children.find(row => row.number === 2);
  if (!course || !river || !child) return;
  return {
    scenario: READER_PRACTICE, behavior: "script" as const, persona_ids: [child.id],
    course_ids: [course.id], component_ids: [river.id], iterations: 1, turn_limit: 2,
    tutor_models: ["gpt-4.1-mini"], tutor_profile_ids: [],
  };
}

export type PracticeTurn = {
  child_text: string;
  session_before?: { scenario_exercised?: boolean; substep?: string; block_id?: string };
  session_after?: { delivery_status?: string; receipt_status?: string; block_id?: string; substep?: string; loop_result?: {
    attempt_counted?: boolean; stayed?: boolean; advanced?: boolean; closed?: string; ended_unit?: boolean;
  } | null };
};

/** Read only the committed grading facts; an absent turn or receipt cannot prove a pass. */
export function readerPracticeChecks(turns: PracticeTurn[]) {
  return [EXAMPLE_REQUEST, CARGO_ANSWER].map(line => {
    const turn = turns.find(item => item.child_text === line && item.session_before?.scenario_exercised);
    if (!turn) return "Not exercised";
    const before = turn.session_before;
    const after = turn.session_after;
    const loop = after?.loop_result;
    const delivered = after?.delivery_status === "delivered" || after?.delivery_status === "recovered";
    if (!delivered || after?.receipt_status !== "committed" || typeof loop?.attempt_counted !== "boolean") return "Outcome unavailable";
    if (loop.attempt_counted) return "An assessment attempt was counted";
    if (!before?.block_id || before.substep !== "central_idea" || !after.block_id || !after.substep || typeof loop.stayed !== "boolean") {
      return "Outcome unavailable";
    }
    if (before.block_id !== after.block_id || after.substep !== "central_idea" || !loop.stayed || loop.advanced || loop.closed || loop.ended_unit) {
      return "Reading question changed";
    }
    return "Central-idea question open · zero attempts used";
  });
}
