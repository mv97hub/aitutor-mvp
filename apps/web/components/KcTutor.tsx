import Link from "next/link";

import { answerKcTurn } from "@/lib/kc-actions";
import type { KcProgress, KcTutorCourse, KcTutorSession } from "@/lib/kc";
import type { Student } from "@/lib/types";

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
    <main className="kc-app">
      <header className="kc-bar">
        <Link href="/">Home</Link>
        <strong>KC Tutor</strong>
        <span>Same child and the same tutor settings as the lesson page.</span>
      </header>
      <div className="kc-tutor">
        <section className="kc-picker">
          {error ? (
            <p className="kc-error" role="alert">
              {error}
            </p>
          ) : null}
          <form method="get" action="/kc-tutor">
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
            <button className="kc-primary" type="submit">
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
              {progress.cards.length === 0 ? <p className="kc-quiet">Every target component is known.</p> : null}
            </>
          ) : null}
        </section>
        <section className="kc-lesson">
          {!session ? <p className="kc-quiet">A card opens one component.</p> : null}
          {session ? (
            <>
              <p className="kc-step">
                {session.title} · {session.recipe} · {session.step_label}
                {session.status === "completed" ? ` · score ${session.score ?? 0}` : ""}
              </p>
              <ol className="kc-transcript" aria-live="polite">
                {session.messages.map((message) => (
                  <li key={message.id} className={message.role}>
                    {message.content}
                  </li>
                ))}
              </ol>
              {session.redirect ? <p className="kc-redirect">Next card: {session.redirect.title}</p> : null}
              {session.status === "completed" ? null : (
                <form action={answerKcTurn}>
                  <input type="hidden" name="session_id" value={session.id} />
                  <input type="hidden" name="student" value={studentId} />
                  <input type="hidden" name="course" value={courseId} />
                  <label>
                    Your answer
                    <textarea aria-label="Your answer" name="answer" rows={3} required />
                  </label>
                  <button className="kc-primary" type="submit">
                    Send
                  </button>
                </form>
              )}
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
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
