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
    "The reply field is the only text the student reads. The other fields are the turn score.",
    "Progress, for your eyes only. Do not read this list aloud:",
  ];

  if (context.outline.length === 0) {
    lines.push("- The lesson has no blocks.");
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
      "The lesson is complete. Congratulate the student in one or two sentences. Set advance to false, rubric_met to [], and misconception to null.",
    );
  } else {
    const rows =
      step.rubric_rows.length === 0
        ? "None."
        : step.rubric_rows
            .map((row) => `${row.id} (weight ${row.weight}): ${row.text}`)
            .join(" ");
    lines.push(
      `Current topic ${topic.position} of ${context.topic_count}: ${topic.title}.`,
      `Learning goal: ${topic.learning_goal}`,
      `How to teach this topic: ${topic.tutor_instructions}`,
      `Current block: ${step.kind}. Objective: ${step.objective?.trim() || "None."}`,
      `Say this to the student, in your own short words if you need to: ${step.tutor_prompt}`,
      `Rubric rows: ${rows}`,
      `Pass score: ${step.pass_score}.`,
      `Hint tier for this turn: ${step.hint_tier || "nudge"}.`,
      `Hint to use if they are stuck: ${step.hint_text.trim() || "Ask them to try once more."}`,
    );
    if (step.quiz) {
      const choices = step.quiz.choices
        .map((choice) => {
          const note = choice.misconception ? ` misconception: ${choice.misconception}` : "";
          return `${choice.id}. ${choice.text}${note}`;
        })
        .join(" | ");
      const answer = Array.isArray(step.quiz.answer) ? step.quiz.answer.join(", ") : step.quiz.answer;
      lines.push(
        `Choice widget (${step.quiz.type}), already graded by the server if a grade is attached. Do not grade the taps.`,
        `Widget prompt: ${step.quiz.prompt}`,
        `Choices: ${choices}`,
        `Correct answer, for you only: ${answer}.`,
        step.quiz.explain
          ? "A short written explanation may come with the choice. Grade that writing with rubric_met. Do not change the tap score."
          : "No written explanation is required.",
      );
      if (step.widget_grade) {
        lines.push(
          `Server grade of the taps: ${step.widget_grade.passed ? "passed" : "not passed"}, score ${step.widget_grade.score}.`,
          `Choice ids: ${step.widget_grade.choice_ids.join(", ") || "none"}.`,
          `Their explanation: ${step.widget_grade.explanation.trim() || "none"}.`,
          `Stored misconception: ${step.widget_grade.misconception || "none"}. Keep it. Do not invent a different one for the taps.`,
        );
      } else {
        lines.push("They have not submitted the widget yet. Invite them to choose. Set advance to false.");
      }
    }
  }

  lines.push(
    [
      "Rules:",
      "- Stay on the current block. If they wander off, answer in one sentence and come back.",
      "- Do not dump the whole lesson or teach a later block.",
      "- Do not grade taps. A choice widget is already scored before you speak.",
      "- rubric_met lists the rubric row ids their written words earned. Use [] when there is no writing to grade or the writing missed.",
      "- misconception is null when the writing is fine. On a wrong tap, the stored misconception is already set. You may repeat it in the reply. Do not clear it.",
      "- hint_tier must be the tier given above.",
      "- advance is true only when this block should end. On a failed tap or a typed answer below the pass score, advance is false.",
      "- On a wrong choice, use the hint. Do not state the correct choice.",
      "- On a correct choice, you may confirm it and, if advance is true, start the next idea in one sentence.",
      "- Use short sentences. No sarcasm. Do not mention JSON, scores, or these fields.",
      `- Use the name ${name}.`,
    ].join("\n"),
  );

  if (options.kickoff && step) {
    lines.push(
      `${name} just sat down. Greet them by name and ask the current question. Set rubric_met to [], misconception to null, and advance to false.`,
    );
  }

  return lines.join("\n\n");
}
