"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { CrayonSession } from "@/components/learn/CrayonSession";
import { KcLesson } from "@/components/learn/KcLesson";
import { LearnQuestPanel, type TutorMood } from "@/components/learn/LearnQuestPanel";
import type { KcProgress, KcTutorSession } from "@/lib/kc";
import { friendlyStrength, topicStars } from "@/lib/learn";
import { learnMobileCoursePath, learnMobileHome, nextOpenTopic } from "@/lib/learn-mobile";
import type { TutorProfile } from "@/lib/types";

export function LearnMobileTutor({
  studentId,
  courseId,
  courseTitle,
  stars,
  progress,
  session,
  error,
  tutor,
  model,
}: {
  studentId: string;
  courseId: string;
  courseTitle: string;
  stars: number;
  progress: KcProgress | null;
  session: KcTutorSession | null;
  error: string | null;
  tutor: TutorProfile;
  model: string;
}) {
  const router = useRouter();
  const [mood, setMood] = useState<TutorMood>("ready");
  const activeId = session?.kc_id || "";
  const nextTopic = nextOpenTopic(progress?.units ?? [], activeId);
  const currentTopic = (progress?.units ?? []).find((unit) => !unit.patch && unit.id === activeId) ?? null;
  const homeHref = learnMobileHome(studentId);

  function openTopic(kcId: string) {
    router.push(learnMobileCoursePath(studentId, courseId, { kc: kcId }));
    router.refresh();
  }

  useEffect(() => {
    const viewport = window.visualViewport;
    const shell = document.querySelector(".cb-session-page");
    if (!viewport || !(shell instanceof HTMLElement)) return;
    const screen = viewport;
    const node = shell;
    function pinToVisibleScreen() {
      node.style.height = `${screen.height}px`;
      node.style.top = `${screen.offsetTop}px`;
    }
    pinToVisibleScreen();
    screen.addEventListener("resize", pinToVisibleScreen);
    screen.addEventListener("scroll", pinToVisibleScreen);
    return () => {
      screen.removeEventListener("resize", pinToVisibleScreen);
      screen.removeEventListener("scroll", pinToVisibleScreen);
    };
  }, []);

  const steps: Array<"done" | "current" | "upcoming"> = (session?.block_progress ?? []).map((item) =>
    item.status === "completed" ? "done" : item.status === "active" ? "current" : "upcoming",
  );
  const topicTitle = currentTopic?.title || session?.title || "Lesson";

  return (
    <CrayonSession
      backHref={homeHref}
      courseTitle={courseTitle}
      topicTitle={topicTitle}
      goal={topicTitle}
      steps={steps}
      tools={<span className="cb-tag">{stars} stars</span>}
      quest={
        <LearnQuestPanel
          tutor={tutor}
          mood={mood}
          progress={progress}
          session={session}
          activeId={activeId}
          onOpenTopic={openTopic}
        />
      }
    >
      {error ? (
        <div className="banner" role="alert">
          <p>{error}</p>
        </div>
      ) : null}
      {session ? (
        <KcLesson
          key={session.id}
          session={session}
          model={model}
          activeTutor={tutor}
          learnMode
          onActivity={setMood}
          nextTopic={nextTopic ? { id: nextTopic.id, title: nextTopic.title } : null}
          homeHref={homeHref}
          topicCompleteStars={currentTopic ? topicStars(currentTopic) : 0}
          topicStrength={friendlyStrength(currentTopic?.what_was_strong)}
          onOpenTopic={openTopic}
          courseDone={Boolean(progress?.course_complete) && session.status === "completed" && !nextTopic}
          hideComposerWhileChoosing
        />
      ) : (
        <p className="cb-muted-copy">{error || "This course is opening."}</p>
      )}
    </CrayonSession>
  );
}
