import { displayChildStatus } from "./learn.ts";
import type { KidQuiz, TutorProfile } from "./types.ts";

export const LEARN_MOBILE = "/learn-mobile";

/** Full-width choice rows on the phone. Keep this aligned with the learn-mobile CSS. */
export const MOBILE_CHOICE_MIN_PX = 48;

export function learnMobileHome(studentId: string): string {
  return `${LEARN_MOBILE}/${studentId}`;
}

export function learnMobileCoursePath(
  studentId: string,
  courseId: string,
  extra?: { session?: string; kc?: string },
): string {
  const params = new URLSearchParams();
  if (extra?.session) params.set("session", extra.session);
  if (extra?.kc && !extra.session) params.set("kc", extra.kc);
  const query = params.toString();
  const path = `${LEARN_MOBILE}/${studentId}/course/${courseId}`;
  return query ? `${path}?${query}` : path;
}

export type LessonComposerInput = {
  status: string;
  needsSpeech: boolean;
  choosing: boolean;
  hideWhileChoosing: boolean;
};

/** Typed composer for an in-progress lesson. The phone hides it while a choice is on screen. */
export function lessonComposerVisible(input: LessonComposerInput): boolean {
  if (input.status === "completed" || input.needsSpeech) return false;
  if (input.hideWhileChoosing && input.choosing) return false;
  return true;
}

export function choiceShowing(input: {
  hasChoice: boolean;
  status: string;
  needsSpeech: boolean;
  settled: boolean;
}): boolean {
  return input.hasChoice && input.status !== "completed" && !input.needsSpeech && !input.settled;
}

export function quizFor(choice: { prompt: string; choices: { id: string; text: string }[] }): KidQuiz {
  return {
    type: "single",
    prompt: choice.prompt,
    choices: choice.choices,
    explain: false,
  };
}

type TopicRow = {
  id: string;
  title: string;
  patch?: boolean;
  child_status?: string;
  status?: string;
  mastery?: string;
};

export function nextOpenTopic<T extends TopicRow>(units: T[], activeId: string): T | null {
  const topics = units.filter((unit) => !unit.patch);
  const topicIndex = topics.findIndex((unit) => unit.id === activeId);
  if (topicIndex < 0) return null;
  return (
    topics
      .slice(topicIndex + 1)
      .find((unit) => displayChildStatus(unit.child_status, unit.status, unit.mastery) !== "Locked") ?? null
  );
}

export function tutorForSession(
  profiles: TutorProfile[],
  session: {
    tutor_profile_id?: string;
    tutor_name?: string;
    tutor_slug?: string;
    tutor_description?: string;
    avatar_preset?: string;
    avatar_url?: string | null;
  } | null,
  preferredId?: string | null,
): TutorProfile {
  const id = session?.tutor_profile_id || preferredId || "";
  const found =
    profiles.find((profile) => profile.id === id || profile.slug === id) ??
    profiles.find((profile) => profile.is_default || profile.id === "default");
  if (found) return found;
  return {
    id: session?.tutor_profile_id || "default",
    name: session?.tutor_name || "Tutor",
    slug: session?.tutor_slug || "default",
    description: session?.tutor_description || "Your guide for this course.",
    avatar_preset: session?.avatar_preset || "default_circle",
    avatar_url: session?.avatar_url ?? null,
    is_default: true,
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
  };
}
