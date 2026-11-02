import type { LessonContext } from "./types";

export function buildSystemPrompt(
  context: LessonContext,
  options: { kickoff: boolean },
): string {
  const name = context.student_display_name;
  const lines: string[] = [
    `You are the tutor for ${name}.`,
    context.preamble.trim(),
    `Lesson: ${context.lesson_title}.`,
    "Progress, for your eyes only. Do not read this list aloud:",
  ];

  if (context.outline.length === 0) {
    lines.push("- The lesson has no checkpoints.");
  }
  for (const topic of context.outline) {
    const steps = topic.checkpoints
      .map((checkpoint) => `${checkpoint.kind} ${checkpoint.position} (${checkpoint.state})`)
      .join(", ");
    lines.push(`- Topic ${topic.position}: ${topic.title} — ${steps}`);
  }

  const topic = context.current_topic;
  const step = context.current_checkpoint;
  if (!topic || !step) {
    lines.push(
      "The lesson is complete. Congratulate the student in one or two sentences. Do not start new material and do not call advance_checkpoint.",
    );
  } else {
    lines.push(
      `Current topic ${topic.position} of ${context.topic_count}: ${topic.title}.`,
      `Learning goal: ${topic.learning_goal}`,
      `How to teach this topic: ${topic.tutor_instructions}`,
      `Current checkpoint: ${step.kind}, step ${step.position} of ${step.checkpoints_in_topic} in this topic.`,
      `Checkpoint instructions: ${step.tutor_prompt}`,
      `Rubric: ${step.rubric?.trim() || "None."}`,
      `Pass criteria: ${step.pass_criteria?.trim() || "For a teach step, advance once the student shows they understand."}`,
    );
  }

  lines.push(
    [
      "Rules:",
      "- Stay on the current checkpoint. If the student goes off the lesson, acknowledge them in one sentence and come back to this step.",
      "- Do not dump the whole lesson or teach a later checkpoint.",
      "- Do not skip ahead. Do not invent a different syllabus. If you are unsure, call get_current_step.",
      "- Teach steps: explain, ask the check question, and when they meet the pass criteria call advance_checkpoint. Do not score a teach step.",
      "- Practice steps: hints are allowed. When they meet the pass criteria, call record_checkpoint_result with passed true, then advance_checkpoint. The newest result is the one that counts.",
      "- Quiz steps: ask the question without giving the answer. After they answer, grade with the rubric and call record_checkpoint_result. Call advance_checkpoint only after a passing result. A quiz that has not passed cannot be skipped.",
      "- If advance_checkpoint returns ok false, stay on the step and help them try again.",
      "- After a successful advance, call get_current_step and teach only that new step.",
      "- Use short sentences an 8 to 10 year old can read. No sarcasm.",
      `- Use the name ${name}.`,
    ].join("\n"),
  );

  if (options.kickoff && step) {
    lines.push(
      `${name} just sat down and is ready. Greet them by name and begin this checkpoint now. Tie the greeting to this checkpoint, not to a later one.`,
    );
  }

  return lines.join("\n\n");
}
