"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

import { BrandMark } from "@/components/BrandMark";
import { NETWORK_WIDTH, NetworkMap, networkHeight } from "@/components/KcNetwork";
import { Block, Button, Crayon, EmptyState, FilterChip, ProgressRing, StackedBar, Tag, TopBar } from "@/components/crayon";
import { ProgressRecommend } from "@/components/progress/ProgressRecommend";
import { ProgressTotals } from "@/components/progress/ProgressTotals";
import type { KcNetwork, KcProgress, KcTutorCourse } from "@/lib/kc";
import { friendlyStrength, learnCoursePath } from "@/lib/learn";
import {
  blockRows,
  childComponentLabel,
  childNoteByCode,
  componentLine,
  componentRecommendations,
  courseRecommendations,
  courseScore,
  courseTotals,
  finishedComponents,
  finishedSentence,
  passedCourseRubric,
  portfolioCount,
  portfolioCourseStatus,
  statusByCode,
  type BlockRow,
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

function stateClass(state: BlockRow["state"]): string {
  if (state === "Passed") return "is-passed";
  if (state === "Revealed") return "is-revealed";
  return "is-not-yet";
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

/** The parent area keeps every link on /parent and hides the link into the child's tutor.
 * Plain strings only: this component is a client component, so a server page cannot pass functions.
 */
export type ProgressArea = {
  backHref: string;
  backLabel: string;
  /** Course cards append ?course=<id> to this path. */
  progressPath: string;
};

function areaCourseHref(area: ProgressArea, courseId: string): string {
  const params = new URLSearchParams();
  params.set("course", courseId);
  return `${area.progressPath}?${params}`;
}

export function KcCourseProgress({
  studentId,
  studentName,
  courses,
  courseId,
  progress,
  network,
  error,
  area,
}: {
  area?: ProgressArea;
  studentId: string;
  studentName: string;
  courses: KcTutorCourse[];
  courseId: string;
  progress: KcProgress | null;
  network: KcNetwork | null;
  error: string | null;
}) {
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [topicFilter, setTopicFilter] = useState<"all" | "mastered" | "learning" | "not-started">("all");
  const detailRef = useRef<HTMLElement>(null);

  useEffect(() => {
    setSelectedCode(null);
    setTopicFilter("all");
  }, [courseId]);

  useEffect(() => {
    if (!selectedCode) return;
    detailRef.current?.scrollIntoView({ block: "nearest" });
  }, [selectedCode]);

  const units = progress?.units ?? [];
  const selected = units.find((unit) => unit.code === selectedCode) ?? null;
  const score = progress ? courseScore(units, progress.known ?? progress.known_count ?? 0) : null;
  const totals = courseTotals(units);
  const revisit = courseRecommendations(units);
  const lastActivity = formatTimestamp(progress?.last_active_at);
  const showed = selected ? showedText(selected) : "";
  const finished = finishedComponents(units);
  const rubric = progress ? passedCourseRubric(progress) : { completed: "", struggled: "" };
  const selectedRows = selected ? blockRows(selected) : [];
  const selectedRecommendations = selected ? componentRecommendations(selected, progress?.opportunities) : null;
  const heading = area ? (
    <header className="parent-work-head">
      <h1>Detailed Progress</h1>
      {studentName ? <p>{studentName}</p> : null}
    </header>
  ) : (
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
  );

  const body = (
    <>
      {heading}

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
                  href={area ? areaCourseHref(area, course.id) : progressPath(studentId, course.id)}
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
          <ProgressTotals
            label="Course totals"
            items={[
              { label: "Components mastered", value: totals.mastered },
              { label: "Components completed", value: totals.completed },
              { label: "Components in progress", value: totals.inProgress },
              { label: "Components not started", value: totals.notStarted },
              { label: "Blocks passed", value: totals.blocksPassed },
              { label: "Blocks revealed", value: totals.blocksRevealed },
              { label: "Blocks not yet", value: totals.blocksNotYet },
            ]}
          />
          {revisit.length > 0 ? (
            <ProgressRecommend heading="Revisit" label="Recommendations">
              <ul>
                {revisit.map((item) => (
                  <li key={item.code}>{item.title}</li>
                ))}
              </ul>
            </ProgressRecommend>
          ) : null}
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
                const line = componentLine(unit);
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
                      {line ? <span className="progress-row-status">{line}</span> : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
          {finished.length > 0 ? (
            <ul className="progress-finished" aria-label="Finished components">
              {finished.map((unit) => {
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
                      <span>{[unit.title, componentLine(unit), updated].filter(Boolean).join(" · ")}</span>
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
          {selected && selectedRecommendations ? (
            <article className="progress-detail" ref={detailRef}>
              <h2>{selected.title}</h2>
              <p>{componentLine(selected)}</p>
              {showed ? <p>{showed}</p> : null}
              {selectedRows.length > 0 ? (
                <ul className="progress-blocks" aria-label="Blocks">
                  {selectedRows.map((row) => (
                    <li key={row.id}>
                      <span className="progress-block-name">{row.name}</span>
                      <span className="progress-block-type">{row.type}</span>
                      <span className={`progress-block-state ${stateClass(row.state)}`}>{row.state}</span>
                      <span className="progress-block-attempts">
                        {row.attempts} {row.attempts === 1 ? "attempt" : "attempts"}
                      </span>
                      {row.firstTry ? <span className="progress-block-first">First try</span> : null}
                    </li>
                  ))}
                </ul>
              ) : null}
              {selectedRecommendations.workOn ||
              selectedRecommendations.misconceptions.length > 0 ||
              selectedRecommendations.opportunities.length > 0 ? (
                <ProgressRecommend heading="Recommendations" level="h3" label="Recommendations">
                  {selectedRecommendations.workOn ? <p>{selectedRecommendations.workOn}</p> : null}
                  {selectedRecommendations.misconceptions.length > 0 ? (
                    <ul aria-label="Misconceptions">
                      {selectedRecommendations.misconceptions.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : null}
                  {selectedRecommendations.opportunities.length > 0 ? (
                    <ul aria-label="Opportunities">
                      {selectedRecommendations.opportunities.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : null}
                </ProgressRecommend>
              ) : null}
              {area ? null : (
                <Link
                  className="learn-text-link"
                  href={learnCoursePath(studentId, courseId, { kc: selected.id })}
                >
                  Continue with your tutor
                </Link>
              )}
            </article>
          ) : null}
        </section>
      ) : null}
    </>
  );

  if (area) return <div className="parent-work progress-page">{body}</div>;

  const topics = units.filter((unit) => !unit.patch);
  const masteredPct =
    progress && progress.total > 0
      ? Math.round((progress.known / progress.total) * 100)
      : topics.length === 0
        ? 0
        : Math.round((totals.mastered / topics.length) * 100);
  const visibleTopics = topics.filter((unit) => {
    const label = childComponentLabel(unit);
    if (topicFilter === "mastered") return label === "Mastered";
    if (topicFilter === "learning") return label === "In Progress";
    if (topicFilter === "not-started") return label === "";
    return true;
  });
  const noPractice = !progress || topics.length === 0;

  return (
    <Crayon>
      <TopBar
        appName="Kinder Computers"
        studentName={studentName}
        items={[
          { href: `/learn/${studentId}`, label: "Home" },
          { href: `/kc-progress?student=${encodeURIComponent(studentId)}`, label: "My Progress", active: true },
        ]}
      />
      <main className="cb-page">
        <div className="cb-chip-row" role="group" aria-label="Courses">
          {courses.map((course) => {
            const selectedCard = course.id === courseId;
            return (
              <Link
                key={course.id}
                href={progressPath(studentId, course.id)}
                className={selectedCard ? "cb-chip is-wide is-blue" : "cb-chip is-wide"}
                aria-pressed={selectedCard}
              >
                {course.title}
              </Link>
            );
          })}
        </div>
        {error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        {noPractice ? (
          <EmptyState title="No practice yet — start a lesson to see your progress here">
            <Button tone="primary" href={`/learn/${studentId}`}>
              Back to lessons
            </Button>
          </EmptyState>
        ) : (
          <>
            <section className="cb-summary" aria-label={progress?.title || "Course"}>
              <Block className="cb-master">
                <ProgressRing value={masteredPct} label={`${masteredPct}% mastered`} />
                <h2>{masteredPct}% mastered</h2>
              </Block>
              <Block>
                <StackedBar
                  segments={[
                    { id: "mastered", label: "Mastered", count: totals.mastered, tone: "green" },
                    { id: "learning", label: "Learning", count: totals.inProgress, tone: "blue" },
                    { id: "started", label: "Started", count: totals.completed, tone: "yellow" },
                    { id: "not-started", label: "Not started", count: totals.notStarted, tone: "track" },
                  ]}
                />
              </Block>
            </section>
            <div className="cb-filters" role="group" aria-label="Topic status">
              {(
                [
                  ["all", "All"],
                  ["mastered", "Mastered"],
                  ["learning", "Learning"],
                  ["not-started", "Not started"],
                ] as const
              ).map(([id, label]) => (
                <FilterChip key={id} pressed={topicFilter === id} onClick={() => setTopicFilter(id)}>
                  {label}
                </FilterChip>
              ))}
            </div>
            <ol className="cb-topic-list">
              {visibleTopics.map((unit) => {
                const label = childComponentLabel(unit);
                const status = label === "In Progress" ? "Learning" : label || "Not started";
                const tone = label === "Mastered" ? "green" : label === "In Progress" ? "sky" : label === "Completed" ? "yellow" : "surface";
                const filled = pipCount(unit);
                const index = topics.findIndex((item) => item.id === unit.id);
                return (
                  <li key={unit.id} className="cb-topic-row">
                    <button
                      type="button"
                      className="cb-topic-main"
                      aria-pressed={unit.code === selectedCode}
                      onClick={() => setSelectedCode(unit.code)}
                    >
                      <span className={`cb-num${label === "Mastered" ? " is-done" : ""}`}>{index + 1}</span>
                      <span>{unit.title}</span>
                    </button>
                    <span className="cb-pips" aria-label={`${filled} of 5 mastery`}>
                      {Array.from({ length: 5 }, (_, pip) => (
                        <i key={pip} className={pip < filled ? "cb-pip is-on" : "cb-pip"} />
                      ))}
                    </span>
                    <Tag tone={tone}>{status}</Tag>
                    <Button href={learnCoursePath(studentId, courseId, { kc: unit.id })}>Practice</Button>
                  </li>
                );
              })}
            </ol>
            {progress && score ? (
              <Block>
                <p className="cb-muted-copy">
                  {score.percent}% · {score.finished} of {score.total}
                  {lastActivity ? ` · Last activity ${lastActivity}` : " · No activity yet"}
                </p>
                <ProgressTotals
                  label="Course totals"
                  items={[
                    { label: "Components mastered", value: totals.mastered },
                    { label: "Components completed", value: totals.completed },
                    { label: "Components in progress", value: totals.inProgress },
                    { label: "Components not started", value: totals.notStarted },
                    { label: "Blocks passed", value: totals.blocksPassed },
                    { label: "Blocks revealed", value: totals.blocksRevealed },
                    { label: "Blocks not yet", value: totals.blocksNotYet },
                  ]}
                />
                {revisit.length > 0 ? (
                  <ProgressRecommend heading="Revisit" label="Recommendations">
                    <ul>
                      {revisit.map((item) => (
                        <li key={item.code}>{item.title}</li>
                      ))}
                    </ul>
                  </ProgressRecommend>
                ) : null}
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
                      <p className="cb-muted-copy">This course has no prerequisite map yet.</p>
                    )}
                  </div>
                </div>
                {finished.length > 0 ? (
                  <ul className="progress-finished" aria-label="Finished components">
                    {finished.map((unit) => {
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
                            <span>{[unit.title, componentLine(unit), updated].filter(Boolean).join(" · ")}</span>
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
                {selected && selectedRecommendations ? (
                  <article className="progress-detail" ref={detailRef}>
                    <h2>{selected.title}</h2>
                    <p>{componentLine(selected)}</p>
                    {showed ? <p>{showed}</p> : null}
                    {selectedRows.length > 0 ? (
                      <ul className="progress-blocks" aria-label="Blocks">
                        {selectedRows.map((row) => (
                          <li key={row.id}>
                            <span className="progress-block-name">{row.name}</span>
                            <span className="progress-block-type">{row.type}</span>
                            <span className={`progress-block-state ${stateClass(row.state)}`}>{row.state}</span>
                            <span className="progress-block-attempts">
                              {row.attempts} {row.attempts === 1 ? "attempt" : "attempts"}
                            </span>
                            {row.firstTry ? <span className="progress-block-first">First try</span> : null}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {selectedRecommendations.workOn ||
                    selectedRecommendations.misconceptions.length > 0 ||
                    selectedRecommendations.opportunities.length > 0 ? (
                      <ProgressRecommend heading="Recommendations" level="h3" label="Recommendations">
                        {selectedRecommendations.workOn ? <p>{selectedRecommendations.workOn}</p> : null}
                        {selectedRecommendations.misconceptions.length > 0 ? (
                          <ul aria-label="Misconceptions">
                            {selectedRecommendations.misconceptions.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        ) : null}
                        {selectedRecommendations.opportunities.length > 0 ? (
                          <ul aria-label="Opportunities">
                            {selectedRecommendations.opportunities.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        ) : null}
                      </ProgressRecommend>
                    ) : null}
                    <Link className="cb-btn" href={learnCoursePath(studentId, courseId, { kc: selected.id })}>
                      Continue with your tutor
                    </Link>
                  </article>
                ) : null}
              </Block>
            ) : null}
          </>
        )}
      </main>
    </Crayon>
  );
}

function pipCount(unit: { p_known?: number; status?: string; mastery?: string }): number {
  if (typeof unit.p_known === "number" && Number.isFinite(unit.p_known)) {
    return Math.max(0, Math.min(5, Math.round(unit.p_known * 5)));
  }
  const label = childComponentLabel(unit);
  if (label === "Mastered") return 5;
  if (label === "Completed") return 4;
  if (label === "In Progress") return 2;
  return 0;
}
