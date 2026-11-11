"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { KcLesson } from "@/components/learn/KcLesson";
import { LearnQuestPanel, type TutorMood } from "@/components/learn/LearnQuestPanel";
import type { KcProgress, KcTutorSession } from "@/lib/kc";
import { friendlyStrength, STAR_TOOLTIP, topicStars } from "@/lib/learn";
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
  const [sheet, setSheet] = useState(false);
  const [mood, setMood] = useState<TutorMood>("ready");
  const activeId = session?.kc_id || "";
  const nextTopic = nextOpenTopic(progress?.units ?? [], activeId);
  const currentTopic = (progress?.units ?? []).find((unit) => !unit.patch && unit.id === activeId) ?? null;
  const homeHref = learnMobileHome(studentId);

  function openTopic(kcId: string) {
    setSheet(false);
    router.push(learnMobileCoursePath(studentId, courseId, { kc: kcId }));
    router.refresh();
  }

  useEffect(() => {
    if (!sheet) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setSheet(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sheet]);

  useEffect(() => {
    const viewport = window.visualViewport;
    const shell = document.querySelector(".learn-mobile-chat");
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

  return (
    <main className="learn-mobile-chat ds-shell">
      <header className="learn-mobile-bar">
        <Link href={homeHref} className="learn-mobile-back">
          ← Back
        </Link>
        <h1>{session?.title || courseTitle}</h1>
        <span className="learn-stars" title={STAR_TOOLTIP}>
          ★ {stars}
        </span>
        <button
          type="button"
          className="learn-mobile-quests"
          aria-expanded={sheet}
          aria-controls="learn-mobile-quest-sheet"
          onClick={() => setSheet(true)}
        >
          Quest map
        </button>
      </header>
      {session ? (
        <>
          {error ? (
            <div className="banner" role="alert">
              <p>{error}</p>
            </div>
          ) : null}
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
        </>
      ) : (
        <div className="ds-empty">
          <p>{error || "This course is opening."}</p>
        </div>
      )}
      {sheet ? (
        <div className="learn-mobile-sheet-root">
          <button type="button" className="learn-mobile-sheet-backdrop" aria-label="Close quest map" onClick={() => setSheet(false)} />
          <div
            id="learn-mobile-quest-sheet"
            className="learn-mobile-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="learn-mobile-quest-title"
          >
            <header>
              <h2 id="learn-mobile-quest-title">Quest map</h2>
              <button type="button" className="learn-btn" onClick={() => setSheet(false)}>
                Close
              </button>
            </header>
            <LearnQuestPanel
              tutor={tutor}
              mood={mood}
              progress={progress}
              session={session}
              activeId={activeId}
              onOpenTopic={openTopic}
            />
          </div>
        </div>
      ) : null}
    </main>
  );
}
