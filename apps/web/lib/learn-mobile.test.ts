import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  LEARN_MOBILE,
  MOBILE_CHOICE_MIN_PX,
  choiceShowing,
  learnMobileCoursePath,
  learnMobileHome,
  lessonComposerVisible,
  nextOpenTopic,
  quizFor,
  tutorForSession,
} from "./learn-mobile.ts";
import type { TutorProfile } from "./types.ts";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

function source(path: string): string {
  return readFileSync(join(webRoot, path), "utf8");
}

test("mobile routes keep the session query and drop the component once a session exists", () => {
  assert.equal(LEARN_MOBILE, "/learn-mobile");
  assert.equal(learnMobileHome("stu"), "/learn-mobile/stu");
  assert.equal(learnMobileCoursePath("stu", "course"), "/learn-mobile/stu/course/course");
  assert.equal(learnMobileCoursePath("stu", "course", { session: "ses" }), "/learn-mobile/stu/course/course?session=ses");
  assert.equal(learnMobileCoursePath("stu", "course", { kc: "topic" }), "/learn-mobile/stu/course/course?kc=topic");
  assert.equal(learnMobileCoursePath("stu", "course", { session: "ses", kc: "topic" }).includes("kc="), false);
});

test("the composer stays on desktop during a choice and hides on the phone", () => {
  const choosing = { status: "in_progress", needsSpeech: false, choosing: true, hideWhileChoosing: false };
  assert.equal(lessonComposerVisible(choosing), true);
  assert.equal(lessonComposerVisible({ ...choosing, hideWhileChoosing: true }), false);
  assert.equal(lessonComposerVisible({ ...choosing, choosing: false, hideWhileChoosing: true }), true);
  assert.equal(lessonComposerVisible({ ...choosing, status: "completed", hideWhileChoosing: false }), false);
  assert.equal(lessonComposerVisible({ ...choosing, needsSpeech: true, choosing: false, hideWhileChoosing: false }), false);
});

test("a choice is showing until the tap is settled or the tutor still needs to speak", () => {
  assert.equal(choiceShowing({ hasChoice: true, status: "in_progress", needsSpeech: false, settled: false }), true);
  assert.equal(choiceShowing({ hasChoice: true, status: "in_progress", needsSpeech: false, settled: true }), false);
  assert.equal(choiceShowing({ hasChoice: true, status: "completed", needsSpeech: false, settled: false }), false);
  assert.equal(choiceShowing({ hasChoice: false, status: "in_progress", needsSpeech: false, settled: false }), false);
  assert.equal(choiceShowing({ hasChoice: true, status: "in_progress", needsSpeech: true, settled: false }), false);
});

test("a tutor choice becomes a single-select card with no typed explanation", () => {
  const quiz = quizFor({ prompt: "Which one?", choices: [{ id: "a", text: "A" }] });
  assert.equal(quiz.type, "single");
  assert.equal(quiz.explain, false);
  assert.equal(quiz.prompt, "Which one?");
  assert.deepEqual(quiz.choices, [{ id: "a", text: "A" }]);
});

test("the next topic skips patches and locked rows", () => {
  const units = [
    { id: "a", title: "A", patch: false, status: "completed" },
    { id: "b", title: "B", patch: false, status: "in_progress" },
    { id: "c", title: "C", patch: true, status: "not_started" },
    { id: "d", title: "D", patch: false, status: "locked", child_status: "Locked" },
    { id: "e", title: "E", patch: false, status: "not_started" },
  ];
  assert.equal(nextOpenTopic(units, "b")?.id, "e");
  assert.equal(nextOpenTopic(units, "missing"), null);
});

test("a known tutor profile wins over the session fallback", () => {
  const profile = {
    id: "fox",
    name: "Fox",
    instructive: 3,
    persona: "coach",
    lexicon: "adaptive_to_child",
    voice_override: false,
    metaphors: "everyday",
    sidekick: "none",
    struggle_window: "standard",
    anti_spoiler: true,
    one_question: true,
    use_interests: true,
    stay_on_course: true,
    growth_praise: true,
    misconception_policy: "explain_and_retry_once",
    self_explanation: true,
    enrichment: "on_request",
  } satisfies TutorProfile;
  assert.equal(tutorForSession([profile], { tutor_profile_id: "fox", tutor_name: "Other" }, null).name, "Fox");
  assert.equal(tutorForSession([], { tutor_name: "Owl" }, null).name, "Owl");
});

test("the lesson component is shared and the phone page hides the composer during a choice", () => {
  const tutor = source("components/KcTutor.tsx");
  const lesson = source("components/learn/KcLesson.tsx");
  const mobile = source("components/learn/LearnMobileTutor.tsx");
  assert.match(tutor, /from "@\/components\/learn\/KcLesson"/);
  assert.equal(tutor.includes("function KcLesson"), false);
  assert.equal(tutor.includes("hideComposerWhileChoosing"), false);
  assert.match(lesson, /lessonComposerVisible/);
  assert.match(lesson, /ChoiceWidget/);
  assert.match(lesson, /learn-star-burst/);
  assert.match(lesson, /learn-next-card/);
  assert.match(lesson, /\/api\/kc\/tutor\/speak/);
  assert.match(lesson, /\/api\/kc\/tutor\/answer/);
  assert.match(mobile, /hideComposerWhileChoosing/);
  assert.equal(mobile.includes("KcDebugPanel"), false);
  assert.equal(mobile.includes("Debug"), false);
});

test("the phone routes redirect to a session and desktop /learn stays on KcTutor", () => {
  const course = source("app/learn-mobile/[studentId]/course/[courseId]/page.tsx");
  const home = source("app/learn-mobile/[studentId]/page.tsx");
  const chooser = source("app/learn-mobile/page.tsx");
  const desktop = source("app/learn/[studentId]/course/[courseId]/page.tsx");
  assert.match(chooser, /\/kc\/tutor\/learners/);
  assert.match(home, /LEARN_MOBILE/);
  assert.match(home, /Detailed progress|kc-progress|ChildHome/);
  assert.match(course, /learnMobileCoursePath/);
  assert.match(course, /redirect\(/);
  assert.match(course, /\/kc\/tutor\/start/);
  assert.equal(course.includes("/kc/tutor/variables"), false);
  assert.equal(course.includes("KcDebugPanel"), false);
  assert.match(desktop, /<KcTutor/);
  assert.equal(desktop.includes("LearnMobileTutor"), false);
  assert.equal(desktop.includes("learn-mobile"), false);
  assert.match(source("lib/menu-pages.ts"), /href: "\/learn-mobile"/);
});

test("phone choice targets are at least 48px and the thread uses the dynamic viewport", () => {
  assert.equal(MOBILE_CHOICE_MIN_PX, 48);
  const css = source("app/globals.css");
  const section = css.slice(css.indexOf("/* learn-mobile */"));
  assert.notEqual(section.indexOf("/* learn-mobile */"), -1);
  assert.match(section, /100dvh/);
  assert.match(section, /safe-area-inset-bottom/);
  assert.match(section, /safe-area-inset-top/);
  assert.match(section, /min-height:\s*48px/);
  assert.match(section, /\.learn-mobile-chat[\s\S]*widget-choice/);
});
