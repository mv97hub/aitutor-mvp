"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { KcBanner } from "@/components/KcBanner";
import { NetworkMap } from "@/components/KcNetwork";
import { type KcNetwork, type KcProgress, type KcTutorCourse } from "@/lib/kc";
import { statusByCode, unitsByStatus, type KcProgressUnit, type KcUnitStatus } from "@/lib/kc-progress";
import type { Student } from "@/lib/types";

const LISTS: { status: KcUnitStatus; title: string }[] = [
  { status: "completed", title: "Completed" },
  { status: "in_progress", title: "In progress" },
  { status: "not_started", title: "Not started" },
];

function progressPath(student: string, course: string) {
  const params = new URLSearchParams();
  if (student) params.set("student", student);
  if (course) params.set("course", course);
  const query = params.toString();
  return query ? `/kc-progress?${query}` : "/kc-progress";
}

function unitType(unit: KcProgressUnit) {
  const name = unit.summary || "No blocks yet";
  return unit.patch ? `${name} patch` : name;
}

export function KcCourseProgress({
  students,
  courses,
  studentId,
  courseId,
  progress,
  network,
  error,
}: {
  students: Student[];
  courses: KcTutorCourse[];
  studentId: string;
  courseId: string;
  progress: KcProgress | null;
  network: KcNetwork | null;
  error: string | null;
}) {
  const router = useRouter();
  const [student, setStudent] = useState(studentId);
  const [course, setCourse] = useState(courseId);

  useEffect(() => {
    setStudent(studentId);
    setCourse(courseId);
  }, [studentId, courseId]);

  function visit(nextStudent: string, nextCourse: string) {
    if (nextStudent === studentId && nextCourse === courseId) {
      router.refresh();
      return;
    }
    router.push(progressPath(nextStudent, nextCourse));
    router.refresh();
  }

  const groups = progress ? unitsByStatus(progress.units) : null;
  const show = Boolean(studentId && courseId && progress && network && groups);

  return (
    <main className="ds-shell kc-screen kc-progress">
      <KcBanner name="KC Course Progress" />
      <section className="kc-progress-body">
        {error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        <form
          className="kc-progress-pick"
          method="get"
          action="/kc-progress"
          onSubmit={(event) => {
            event.preventDefault();
            visit(student, course);
          }}
        >
          <label>
            Child
            <select
              aria-label="Choose a child"
              name="student"
              value={student}
              onChange={(event) => {
                const next = event.target.value;
                setStudent(next);
                visit(next, course);
              }}
            >
              <option value="">Choose a child</option>
              {students.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.display_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Course
            <select
              aria-label="Choose a ready course"
              name="course"
              value={course}
              onChange={(event) => {
                const next = event.target.value;
                setCourse(next);
                visit(student, next);
              }}
            >
              <option value="">Choose a ready course</option>
              {courses.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
          </label>
          <button className="button" type="submit">
            Show
          </button>
        </form>
        {show && progress && network && groups ? (
          <>
            <p className="kc-progress-score">
              <strong>{progress.percent}%</strong>
              <span>{progress.count_label}</span>
            </p>
            <section className="kc-progress-map" aria-label={`${progress.title} network`}>
              <h2>Network</h2>
              <ul className="kc-progress-legend">
                <li>
                  <span className="kc-progress-swatch is-completed" />
                  Completed
                </li>
                <li>
                  <span className="kc-progress-swatch is-in-progress" />
                  In progress
                </li>
                <li>
                  <span className="kc-progress-swatch is-not-started" />
                  Not started
                </li>
                <li>
                  <span className="kc-progress-swatch is-patch" />
                  Patch
                </li>
              </ul>
              <NetworkMap network={network} statusByCode={statusByCode(progress.units)} />
            </section>
            <div className="kc-progress-lists">
              {LISTS.map((list) => {
                const rows = groups[list.status];
                return (
                  <section key={list.status} aria-label={list.title}>
                    <h2>{list.title}</h2>
                    {rows.length === 0 ? <p className="ds-quiet">None</p> : null}
                    <ul>
                      {rows.map((unit) => (
                        <li key={unit.id}>
                          <strong>{unit.title}</strong>
                          <span>{unitType(unit)}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                );
              })}
            </div>
          </>
        ) : null}
      </section>
    </main>
  );
}
