"use client";

import { useEffect, useRef, useState, useTransition } from "react";

import { KcBanner } from "@/components/KcBanner";
import { ChoiceWidget } from "@/components/LessonBlocks";
import { answerKcTurn } from "@/lib/kc-actions";
import type { KcProgress, KcTutorCourse, KcTutorSession } from "@/lib/kc";
import type { KidQuiz, Student } from "@/lib/types";
import { useRouter } from "next/navigation";

export function KcTutor({
  students,
  courses,
  studentId,
  courseId,
  progress,
  session,
  error,
}: {
  students: Student[];
  courses: KcTutorCourse[];
  studentId: string;
  courseId: string;
  progress: KcProgress | null;
  session: KcTutorSession | null;
  error: string | null;
}) {
  const course = courses.find((item) => item.id === courseId) ?? null;
  return (
    <main className="ds-shell kc-screen">
      <KcBanner name="KC Tutor" />
      <aside className="ds-side">
        {error && !session ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        <form className="kc-tutor-pick" method="get" action="/kc-tutor">
          <label>
            Child
            <select aria-label="Choose a child" name="student" defaultValue={studentId}>
              <option value="">Choose a child</option>
              {students.map((student) => (
                <option key={student.id} value={student.id}>
                  {student.display_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Course
            <select aria-label="Choose a course" name="course" defaultValue={courseId}>
              <option value="">Choose a ready course</option>
              {courses.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
          </label>
          <button className="button" type="submit">
            Open
          </button>
        </form>
        {progress ? (
          <>
            <Ring progress={progress} />
            {course?.kind === "time_boxed" && progress.minutes ? (
              <p className="kc-minutes">{progress.minutes} minutes</p>
            ) : null}
            <ul className="kc-cards" aria-label="Next work">
              {progress.cards.map((card) => (
                <li key={card.role}>
                  <a href={`/kc-tutor?student=${studentId}&course=${courseId}&kc=${card.id}`}>
                    <span>{card.label}</span>
                    <strong>{card.title}</strong>
                    <small>{card.reason}</small>
                  </a>
                </li>
              ))}
            </ul>
            {progress.cards.length === 0 ? <p className="ds-quiet">Every target component is known.</p> : null}
          </>
        ) : null}
      </aside>
      <section className="ds-stage">
        {session ? (
          <header className="ds-header">
            <p className="kc-step">
              {session.title} · {session.recipe} · {session.step_label}
              {session.status === "completed" ? ` · score ${session.score ?? 0}` : ""}
            </p>
          </header>
        ) : null}
        {session?.redirect ? <p className="kc-redirect">Next card: {session.redirect.title}</p> : null}
        {!session ? <div className="ds-empty"><p>A card opens one component.</p></div> : null}
        {session ? (
          <KcLesson
            key={`${session.id}:${session.step}:${session.messages.length}:${session.status}`}
            session={session}
            studentId={studentId}
            courseId={courseId}
          />
        ) : null}
      </section>
    </main>
  );
}

function KcLesson({
  session,
  studentId,
  courseId,
}: {
  session: KcTutorSession;
  studentId: string;
  courseId: string;
}) {
  const router = useRouter();
  const started = useRef("");
  const [speakError, setSpeakError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [speaking, setSpeaking] = useState(false);
  const [settled, setSettled] = useState<{ ids: string[]; note: string } | null>(null);
  const [pending, startTransition] = useTransition();
  const anchor = [...session.messages].reverse().find((message) => message.role === "assistant");
  const quiz = session.choice ? quizFor(session.choice) : null;
  const choosing = Boolean(quiz) && session.status !== "completed" && !session.needs_speech && !settled;

  useEffect(() => {
    if (!session.needs_speech) return;
    const key = `${session.id}:${session.step}:${session.messages.length}:${attempt}`;
    if (started.current === key) return;
    started.current = key;
    const controller = new AbortController();
    let cancelled = false;
    setSpeaking(true);
    setSpeakError(null);
    void fetch("/api/kc/tutor/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId: session.id }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const text = (await response.text()).trim();
          throw new Error(text || "The tutor could not say this step.");
        }
        if (!cancelled) router.refresh();
      })
      .catch((err: unknown) => {
        if (cancelled || (err instanceof DOMException && err.name === "AbortError")) return;
        setSpeakError(err instanceof Error ? err.message : "The tutor could not say this step.");
      })
      .finally(() => {
        if (!cancelled) setSpeaking(false);
      });
    return () => {
      cancelled = true;
      controller.abort();
      if (started.current === key) started.current = "";
    };
  }, [attempt, router, session.id, session.messages.length, session.needs_speech, session.step]);

  function sendChoice(transcript: string) {
    const data = new FormData();
    data.set("session_id", session.id);
    data.set("student", studentId);
    data.set("course", courseId);
    data.set("answer", transcript);
    startTransition(() => {
      void answerKcTurn(data);
    });
  }

  return (
    <>
      <div className="ds-scroll" role="log" aria-live="polite" aria-relevant="additions">
        <div className="ds-column">
          {session.messages.map((message) => (
            <div key={message.id}>
              <div className={`bubble ${message.role === "user" ? "user" : "assistant"}`}>
                <p>{message.content}</p>
              </div>
              {quiz && anchor?.id === message.id ? (
                <article
                  className="bubble assistant widget-message"
                  aria-label={settled ? "Your choice" : "Choose an answer"}
                >
                  <ChoiceWidget
                    quiz={quiz}
                    busy={pending}
                    settled={settled}
                    onSubmit={(choice, explanation, transcript) => {
                      const ids = Array.isArray(choice) ? choice : [choice];
                      setSettled({ ids, note: explanation });
                      sendChoice(transcript);
                    }}
                  />
                </article>
              ) : null}
            </div>
          ))}
        </div>
      </div>
      {speaking ? <p className="ds-typing">Tutor is writing…</p> : null}
      {speakError ? (
        <div className="banner" role="alert">
          <p>{speakError}</p>
          <button type="button" className="ghost" onClick={() => setAttempt((value) => value + 1)}>
            Try again
          </button>
        </div>
      ) : null}
      {session.status === "completed" || session.needs_speech ? null : (
        <form
          className="ds-composer-seat"
          action={answerKcTurn}
          onSubmit={(event) => {
            if (choosing) event.preventDefault();
          }}
        >
          <input type="hidden" name="session_id" value={session.id} />
          <input type="hidden" name="student" value={studentId} />
          <input type="hidden" name="course" value={courseId} />
          <div className="ds-card">
            <textarea
              className="ds-draft"
              name="answer"
              rows={1}
              required={!choosing}
              placeholder={choosing ? "Choose an answer above" : "Message"}
              aria-label="Your answer"
              disabled={choosing || pending}
              maxLength={2000}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  if (!choosing) event.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <div className="ds-card-row">
              <button className="ds-send" type="submit" aria-label="Send" disabled={choosing || pending}>
                ↑
              </button>
            </div>
          </div>
        </form>
      )}
    </>
  );
}

function quizFor(choice: { prompt: string; choices: { id: string; text: string }[] }): KidQuiz {
  return {
    type: "single",
    prompt: choice.prompt,
    choices: choice.choices,
    explain: false,
  };
}

function Ring({ progress }: { progress: KcProgress }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const count = Math.max(progress.ring.length, 1);
  const gap = 6;
  const segment = circumference / count;
  const color = {
    known: "#1d6b45",
    fragile: "#c4491d",
    not_started: "#d5cbbd",
  };
  return (
    <figure className="kc-ring">
      <svg viewBox="0 0 140 140" role="img" aria-label={`${progress.count_label} known`}>
        {progress.ring.map((item, index) => (
          <circle
            key={item.id}
            cx="70"
            cy="70"
            r={radius}
            fill="none"
            stroke={color[item.status]}
            strokeWidth="12"
            strokeDasharray={`${Math.max(segment - gap, 1)} ${circumference}`}
            strokeDashoffset={-index * segment}
            transform="rotate(-90 70 70)"
          />
        ))}
        <text x="70" y="74" textAnchor="middle">
          {progress.count_label}
        </text>
      </svg>
      <figcaption>
        {progress.known} known
        {progress.ring.some((item) => item.status === "fragile") ? " · some fragile" : ""}
      </figcaption>
    </figure>
  );
}
