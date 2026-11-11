"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

import { BrandMark } from "@/components/BrandMark";
import { NETWORK_WIDTH, NetworkMap, networkHeight } from "@/components/KcNetwork";
import type { KcNetwork, KcProgress, KcTutorCourse } from "@/lib/kc";
import { friendlyStrength, learnCoursePath } from "@/lib/learn";
import {
  blockScore,
  childComponentLabel,
  childNoteByCode,
  courseScore,
  finishedComponents,
  finishedSentence,
  passedCourseRubric,
  portfolioCount,
  portfolioCourseStatus,
  statusByCode,
  type KcProgressUnit,
  type KcUnitStatus,
} from "@/lib/kc-progress";

function progressPath(student: string, course: string) {
  const params = new URLSearchParams();
  if (student) params.set("student", student);
  if (course) params.set("course", course);
  const query = params.toString();
  return query ? `/kc-progress?${query}` : "/kc-progress";
}

function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function showedText(unit: KcProgressUnit): string {
  const raw = (unit.what_was_strong || unit.result?.strong || unit.strengths || unit.close_text || "").trim();
  if (!raw) return "";
  const cleaned = friendlyStrength(raw);
  if (/fragile|failed/i.test(cleaned)) return "You finished this topic.";
  return cleaned;
}

function componentScore(unit: KcProgressUnit): string {
  const label = childComponentLabel(unit);
  const done = unit.finished_blocks ?? unit.completed_blocks ?? 0;
  const total = unit.total_blocks ?? 0;
  const count = total > 0 ? `${done} of ${total}` : "";
  return [label, count].filter(Boolean).join(" · ");
}

function NetworkFrame({
  network,
  statuses,
  noteByCode,
  selectedCode,
  onSelectNode,
  resetKey,
}: {
  network: KcNetwork;
  statuses: Record<string, KcUnitStatus>;
  noteByCode: Record<string, string>;
  selectedCode: string | null;
  onSelectNode: (code: string) => void;
  resetKey: string;
}) {
  const frame = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [fit, setFit] = useState(1);
  const [box, setBox] = useState(360);
  const width = NETWORK_WIDTH;
  const height = networkHeight(network);

  useEffect(() => {
    setZoom(1);
  }, [resetKey]);

  useEffect(() => {
    const node = frame.current;
    if (!node) return;
    const measure = () => {
      const maxH = Math.min(window.innerHeight * 0.62, 560);
      const next = Math.min(node.clientWidth / width, maxH / height);
      const safe = next > 0 && Number.isFinite(next) ? next : 1;
      setFit(safe);
      setBox(zoom === 1 ? Math.min(height * safe, maxH) : maxH);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [width, height, resetKey, zoom]);

  const scale = fit * zoom;
  return (
    <div className="kc-progress-frame">
      <div className="kc-progress-zoom" role="group" aria-label="Network zoom">
        <button type="button" className="button" onClick={() => setZoom((value) => Math.min(4, value * 1.25))}>
          Zoom in (+)
        </button>
        <button type="button" className="button" onClick={() => setZoom((value) => Math.max(0.25, value / 1.25))}>
          Zoom out (-)
        </button>
        <button type="button" className="button" onClick={() => setZoom(1)}>
          Fit
        </button>
      </div>
      <div
        ref={frame}
        className="kc-progress-viewport"
        style={{ height: box, maxHeight: "min(62vh, 560px)", overflow: zoom === 1 ? "hidden" : "auto" }}
      >
        <NetworkMap
          network={network}
          statusByCode={statuses}
          noteByCode={noteByCode}
          selectedCode={selectedCode}
          onSelectNode={onSelectNode}
          style={{ width: width * scale, height: height * scale }}
        />
      </div>
    </div>
  );
}

export function KcCourseProgress({
  studentId,
  studentName,
  courses,
  courseId,
  progress,
  network,
  error,
}: {
  studentId: string;
  studentName: string;
  courses: KcTutorCourse[];
  courseId: string;
  progress: KcProgress | null;
  network: KcNetwork | null;
  error: string | null;
}) {
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const detailRef = useRef<HTMLElement>(null);

  useEffect(() => {
    setSelectedCode(null);
  }, [courseId]);

  useEffect(() => {
    if (!selectedCode) return;
    detailRef.current?.scrollIntoView({ block: "nearest" });
  }, [selectedCode]);

  const units = progress?.units ?? [];
  const selected = units.find((unit) => unit.code === selectedCode) ?? null;
  const score = progress ? courseScore(units, progress.known ?? progress.known_count ?? 0) : null;
  const lastActivity = formatTimestamp(progress?.last_active_at);
  const showed = selected ? showedText(selected) : "";
  const finished = finishedComponents(units);
  const rubric = progress ? passedCourseRubric(progress) : { completed: "", struggled: "" };

  return (
    <main className="learn-shell progress-page">
      <header className="progress-bar">
        <BrandMark />
        <div className="progress-title">
          <h1>Detailed Progress</h1>
          {studentName ? <p>{studentName}</p> : null}
        </div>
        <Link className="learn-text-link" href={`/learn/${studentId}`}>
          Back to home
        </Link>
      </header>

      <section className="learn-section progress-portfolio-section" aria-label="Course Portfolio">
        <h2>Course Portfolio</h2>
        {courses.length === 0 ? (
          <p className="learn-quiet">No courses yet.</p>
        ) : (
          <div className="progress-portfolio">
            {courses.map((course) => {
              const status = portfolioCourseStatus(course);
              const selectedCard = course.id === courseId;
              return (
                <Link
                  key={course.id}
                  href={progressPath(studentId, course.id)}
                  className={selectedCard ? "progress-card is-selected" : "progress-card"}
                  aria-current={selectedCard ? "true" : undefined}
                >
                  <strong>{course.title}</strong>
                  {status ? <span>{status}</span> : null}
                  <span>{portfolioCount(course)}</span>
                </Link>
              );
            })}
          </div>
        )}
      </section>

      {error ? (
        <div className="banner" role="alert">
          <p>{error}</p>
        </div>
      ) : null}

      {progress && score ? (
        <section className="progress-course" aria-label={progress.title}>
          <p className="progress-score">
            {score.percent}% · {score.finished} of {score.total}
            {lastActivity ? ` · Last activity ${lastActivity}` : " · No activity yet"}
          </p>
          <div className="progress-split">
            <div className="progress-map">
              {network && network.nodes.length > 0 ? (
                <NetworkFrame
                  network={network}
                  statuses={statusByCode(units)}
                  noteByCode={childNoteByCode(units)}
                  selectedCode={selectedCode}
                  onSelectNode={setSelectedCode}
                  resetKey={courseId}
                />
              ) : (
                <p className="learn-quiet">This course has no prerequisite map yet.</p>
              )}
            </div>
            <ul className="progress-list" aria-label="Course components">
              {units.map((unit) => {
                const label = childComponentLabel(unit);
                const pressed = unit.code === selectedCode;
                return (
                  <li key={unit.id}>
                    <button
                      type="button"
                      className={pressed ? "is-selected" : undefined}
                      aria-pressed={pressed}
                      onClick={() => setSelectedCode(unit.code)}
                    >
                      <span>{unit.title}</span>
                      {label ? <span className="progress-row-status">{label}</span> : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
          {finished.length > 0 ? (
            <ul className="progress-finished" aria-label="Finished components">
              {finished.map((unit) => {
                const label = childComponentLabel(unit);
                const updated = formatTimestamp(unit.updated_at || unit.completed_at);
                const sentence = finishedSentence(unit, progress.accomplishments);
                const pressed = unit.code === selectedCode;
                return (
                  <li key={unit.id}>
                    <button
                      type="button"
                      className={pressed ? "is-selected" : undefined}
                      aria-pressed={pressed}
                      onClick={() => setSelectedCode(unit.code)}
                    >
                      <span>{[unit.title, label, blockScore(unit), updated].filter(Boolean).join(" · ")}</span>
                      {sentence ? <span className="progress-finished-sentence">{sentence}</span> : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : null}
          {finished.length > 0 && progress.course_complete && (rubric.completed || rubric.struggled) ? (
            <div className="progress-rubric">
              {rubric.completed ? <p>{rubric.completed}</p> : null}
              {rubric.struggled ? <p>{rubric.struggled}</p> : null}
            </div>
          ) : null}
          {selected ? (
            <article className="progress-detail" ref={detailRef}>
              <h2>{selected.title}</h2>
              <p>{componentScore(selected)}</p>
              {showed ? <p>{showed}</p> : null}
              <Link
                className="learn-text-link"
                href={learnCoursePath(studentId, courseId, { kc: selected.id })}
              >
                Continue with your tutor
              </Link>
            </article>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
