"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { KcBanner } from "@/components/KcBanner";
import { NETWORK_WIDTH, NetworkMap, networkHeight } from "@/components/KcNetwork";
import { type KcNetwork, type KcProgress, type KcTutorCourse } from "@/lib/kc";
import {
  masteryByCode,
  statusByCode,
  unitLine,
  unitsByStatus,
  type KcUnitStatus,
} from "@/lib/kc-progress";
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

function finishedTargets(progress: KcProgress) {
  const targets = progress.units.filter((unit) => !unit.patch);
  if (targets.length === 0 || targets.some((unit) => unit.status !== "completed")) return null;
  return {
    gaps: targets.some((unit) => unit.mastery !== "known"),
    targets,
  };
}

function NetworkFrame({
  network,
  statusByCode: statuses,
  noteByCode,
  resetKey,
}: {
  network: KcNetwork;
  statusByCode: Record<string, KcUnitStatus>;
  noteByCode: Record<string, string>;
  resetKey: string;
}) {
  const frame = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [fit, setFit] = useState(1);
  const width = NETWORK_WIDTH;
  const height = networkHeight(network);

  useEffect(() => {
    setZoom(1);
  }, [resetKey]);

  useEffect(() => {
    const node = frame.current;
    if (!node) return;
    const measure = () => {
      const next = Math.min(node.clientWidth / width, node.clientHeight / height);
      setFit(next > 0 && Number.isFinite(next) ? next : 1);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [width, height, resetKey]);

  const scale = fit * zoom;
  return (
    <div className="kc-progress-frame">
      <div className="kc-progress-zoom" role="group" aria-label="Network zoom">
        <button type="button" className="button" onClick={() => setZoom((value) => Math.min(4, value * 1.25))}>
          Zoom in
        </button>
        <button type="button" className="button" onClick={() => setZoom((value) => Math.max(0.25, value / 1.25))}>
          Zoom out
        </button>
        <button type="button" className="button" onClick={() => setZoom(1)}>
          Fit
        </button>
      </div>
      <div ref={frame} className="kc-progress-viewport" style={{ overflow: zoom === 1 ? "hidden" : "auto" }}>
        <NetworkMap
          network={network}
          statusByCode={statuses}
          noteByCode={noteByCode}
          style={{ width: width * scale, height: height * scale }}
        />
      </div>
    </div>
  );
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
  const finished = progress ? finishedTargets(progress) : null;

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
            {finished ? (
              <section className="kc-progress-result" aria-label={finished.gaps ? "Finished with gaps" : "Finished"}>
                <h2>{finished.gaps ? "Finished with gaps" : "Finished"}</h2>
                <p>
                  Known means every counting block passed. Fragile means a required block was revealed. A curiosity
                  block counts only when that setting is on.
                </p>
                <ul>
                  {finished.targets.map((unit) => (
                    <li key={unit.id}>
                      <strong>{unit.title}</strong>
                      {(unit.rubric ?? []).filter((line) => line.trim()).map((line, index) => (
                        <span key={`${unit.id}-rubric-${index}`}>{line}</span>
                      ))}
                      <span>What was strong. {unit.result?.strong || "None stored."}</span>
                      <span>What to work on. {unit.result?.work_on || "None stored."}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
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
              <NetworkFrame
                network={network}
                statusByCode={statusByCode(progress.units)}
                noteByCode={masteryByCode(progress.units)}
                resetKey={`${studentId}:${courseId}`}
              />
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
                          <span>{unitLine(unit)}</span>
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
