"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { KcBanner } from "@/components/KcBanner";
import { NETWORK_WIDTH, NetworkMap, networkHeight } from "@/components/KcNetwork";
import {
  type KcAccomplishmentItem,
  type KcBlockDetail,
  type KcNetwork,
  type KcOpportunityItem,
  type KcProgress,
  type KcTutorCourse,
} from "@/lib/kc";
import {
  CHALLENGE_APPETITE_OPTIONS,
  EXPLANATION_STYLE_OPTIONS,
  GRADE_BAND_OPTIONS,
  INTEREST_TAG_OPTIONS,
} from "@/lib/kc-layer-fields";
import {
  courseScore,
  masteryByCode,
  statusByCode,
  unitLine,
  unitsByStatus,
  type KcProgressUnit,
  type KcUnitStatus,
} from "@/lib/kc-progress";
import type { Student } from "@/lib/types";

type RosterFilter = "all" | "known" | "fragile" | "in_progress" | "not_started";
type CourseFilter = "active_completed" | "all";
type BannerScope = "selected_course" | "all_courses";

const LISTS: { status: KcUnitStatus; title: string }[] = [
  { status: "completed", title: "Completed" },
  { status: "in_progress", title: "In progress" },
  { status: "not_started", title: "Not started" },
];

function optionLabel(options: readonly (readonly [string, string])[], value: string | undefined): string {
  if (!value) return "";
  const hit = options.find(([id]) => id === value);
  if (!hit) return value.replace(/_/g, " ");
  return hit[1].split(" (")[0];
}

function progressPath(student: string, course: string) {
  const params = new URLSearchParams();
  if (student) params.set("student", student);
  if (course) params.set("course", course);
  const query = params.toString();
  return query ? `/kc-progress?${query}` : "/kc-progress";
}

function tutorComponentHref(studentId: string, courseId: string, kcId: string | number) {
  const params = new URLSearchParams();
  if (studentId) params.set("student", studentId);
  if (courseId) params.set("course", courseId);
  if (kcId) params.set("kc", String(kcId));
  return `/kc-tutor?${params.toString()}`;
}

function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "No activity yet";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function kindLabel(kind: string | undefined): string {
  if (kind === "time_boxed") return "Time-Boxed";
  if (kind === "curiosity") return "Curiosity";
  return "Mastery";
}

function unitDisplayStatus(unit: KcProgressUnit): "known" | "fragile" | "in_progress" | "not_started" {
  if (unit.status === "completed") {
    return unit.mastery === "fragile" ? "fragile" : "known";
  }
  if (unit.status === "in_progress") return "in_progress";
  return "not_started";
}

function unitBadgeText(unit: KcProgressUnit): string {
  const ds = unitDisplayStatus(unit);
  if (ds === "known") return "Known";
  if (ds === "fragile") return "Fragile";
  if (ds === "in_progress") return "In Progress";
  return "Not Started";
}

function courseOverallStatus(progress: KcProgress): { label: string; tone: "known" | "fragile" | "in_progress" | "not_started" } {
  const targets = progress.units.filter((u) => !u.patch);
  if (targets.length === 0) return { label: "Not Started", tone: "not_started" };
  const allCompleted = targets.every((u) => u.status === "completed");
  if (allCompleted) {
    const anyFragile = targets.some((u) => u.mastery === "fragile");
    return anyFragile
      ? { label: "Completed with Fragile Concepts", tone: "fragile" }
      : { label: "Mastered", tone: "known" };
  }
  const anyStarted = targets.some((u) => u.status === "completed" || u.status === "in_progress");
  if (anyStarted) return { label: "In Progress", tone: "in_progress" };
  return { label: "Not Started", tone: "not_started" };
}

function defaultSelectedUnit(units: KcProgressUnit[]): KcProgressUnit | null {
  if (!units.length) return null;
  const targets = units.filter((u) => !u.patch);
  const pool = targets.length ? targets : units;
  return (
    pool.find((u) => u.status === "in_progress") ??
    pool.find((u) => u.status === "completed" && u.mastery === "fragile") ??
    pool.find((u) => u.status === "completed" && u.mastery === "known") ??
    pool[0] ??
    null
  );
}

function NetworkFrame({
  network,
  statusByCode: statuses,
  noteByCode,
  selectedCode,
  onSelectNode,
  resetKey,
}: {
  network: KcNetwork;
  statusByCode: Record<string, KcUnitStatus>;
  noteByCode: Record<string, string>;
  selectedCode: string | null;
  onSelectNode: (code: string) => void;
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
          Zoom in (+)
        </button>
        <button type="button" className="button" onClick={() => setZoom((value) => Math.max(0.25, value / 1.25))}>
          Zoom out (-)
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
          selectedCode={selectedCode}
          onSelectNode={onSelectNode}
          style={{ width: width * scale, height: height * scale }}
        />
      </div>
    </div>
  );
}

function statusLabel(unit: KcProgressUnit) {
  if (unit.mastery === "known" || unit.mastery === "fragile") return unit.mastery;
  if (unit.status === "in_progress") return "in progress";
  return "not started";
}

function attemptLabel(count: number) {
  return count === 1 ? "1 attempt" : `${count} attempts`;
}

function ComponentPopup({ unit, onClose }: { unit: KcProgressUnit; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const node = dialog.current;
    if (!node || node.open) return;
    node.showModal();
  }, [unit.id]);

  const blocks = (unit.blocks ?? []).filter((block) => {
    if (unit.status === "in_progress") return block.status === "completed" || block.status === "active";
    return block.status !== "active" || Boolean(block.outcome);
  });
  const close = unit.result;
  const finished = unit.finished_blocks ?? 0;
  const total = unit.total_blocks ?? 0;

  return (
    <dialog
      ref={dialog}
      className="kc-progress-popup"
      aria-label={`${unit.title} score`}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === dialog.current) onClose();
      }}
    >
      <h2>{unit.title}</h2>
      <p>
        {statusLabel(unit)} · {finished} of {total} blocks
      </p>
      {blocks.length ? (
        <ul>
          {blocks.map((block) => (
            <li key={block.id}>
              <strong>{block.type_label || block.type}</strong>
              {block.status === "active" ? <span>Active</span> : null}
              {block.outcome ? <span>{block.outcome}</span> : null}
              {typeof block.attempts === "number" ? <span>{attemptLabel(block.attempts)}</span> : null}
              {block.rubric?.trim() ? <span>{block.rubric}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {close?.strong?.trim() ? <p>What was strong. {close.strong}</p> : null}
      {close?.work_on?.trim() ? <p>What to work on. {close.work_on}</p> : null}
      {close?.justification?.trim() ? <p>Score justification. {close.justification}</p> : null}
      <button className="button" type="button" onClick={onClose}>
        Close
      </button>
    </dialog>
  );
}

function blockOutcomePill(block: KcBlockDetail): { text: string; tone: string } {
  if (block.outcome === "passed") {
    if (block.passed_on_first_try || block.attempts <= 1) {
      return { text: "Passed on 1st try", tone: "is-known" };
    }
    return { text: `Passed (${block.attempts} attempts)`, tone: "is-known" };
  }
  if (block.outcome === "revealed" || block.status === "revealed") {
    return { text: "Revealed → Fragile", tone: "is-fragile" };
  }
  if (block.status === "active") {
    return { text: "Active Now", tone: "is-in-progress" };
  }
  return { text: "Upcoming", tone: "is-not-started" };
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
  const [bannerScope, setBannerScope] = useState<BannerScope>("selected_course");
  const [courseFilter, setCourseFilter] = useState<CourseFilter>("all");
  const [rosterFilter, setRosterFilter] = useState<RosterFilter>("all");
  const [rosterQuery, setRosterQuery] = useState("");
  const [selectedCode, setSelectedCode] = useState<string | null>(() => {
    const first = progress ? defaultSelectedUnit(progress.units) : null;
    return first?.code ?? null;
  });
  const [openUnit, setOpenUnit] = useState<KcProgressUnit | null>(null);

  useEffect(() => {
    setStudent(studentId);
    setCourse(courseId);
  }, [studentId, courseId]);

  useEffect(() => {
    setOpenUnit(null);
    if (!progress) {
      setSelectedCode(null);
      return;
    }
    setSelectedCode((prev) => {
      if (prev && progress.units.some((u) => u.code === prev)) return prev;
      return defaultSelectedUnit(progress.units)?.code ?? null;
    });
  }, [studentId, courseId, progress]);

  function visit(nextStudent: string, nextCourse: string) {
    if (nextStudent === studentId && nextCourse === courseId) {
      router.refresh();
      return;
    }
    router.push(progressPath(nextStudent, nextCourse));
    router.refresh();
  }

  const activeLearner = useMemo(
    () => students.find((item) => item.id === student) ?? students.find((item) => item.id === studentId) ?? null,
    [students, student, studentId],
  );

  // Portfolio-wide KPI rollup across courses
  const portfolioStats = useMemo(() => {
    let completedCourses = 0;
    let inProgressCourses = 0;
    let knownTotal = 0;
    let fragileTotal = 0;
    let completedBlocksTotal = 0;
    let firstTryBlocksTotal = 0;

    for (const c of courses) {
      const compCnt = c.component_count ?? 0;
      const doneCnt = c.completed_count ?? 0;
      const inProgCnt = c.in_progress_count ?? 0;
      if (compCnt > 0 && doneCnt >= compCnt) {
        completedCourses += 1;
      } else if (doneCnt > 0 || inProgCnt > 0) {
        inProgressCourses += 1;
      }
      knownTotal += c.known_count ?? 0;
      fragileTotal += c.fragile_count ?? 0;
      completedBlocksTotal += c.completed_blocks_count ?? 0;
      firstTryBlocksTotal += c.first_try_pass_count ?? 0;
    }

    if (courses.length === 0 && progress) {
      knownTotal = progress.known_count ?? progress.known;
      fragileTotal = progress.fragile_count ?? 0;
      completedBlocksTotal = progress.completed_blocks_count ?? 0;
      firstTryBlocksTotal = progress.first_try_pass_count ?? 0;
    }

    const accuracyPct =
      completedBlocksTotal > 0 ? Math.round((firstTryBlocksTotal * 100) / completedBlocksTotal) : 0;

    return {
      completedCourses,
      inProgressCourses,
      knownTotal,
      fragileTotal,
      completedBlocksTotal,
      firstTryBlocksTotal,
      accuracyPct,
    };
  }, [courses, progress]);

  const accomplishmentsList = useMemo((): (KcAccomplishmentItem & { courseId?: string; courseTitle?: string })[] => {
    if (bannerScope === "selected_course" && progress) {
      return (progress.accomplishments ?? []).map((item) => ({
        ...item,
        courseId: progress.course_id,
        courseTitle: progress.title,
      }));
    }
    const items: (KcAccomplishmentItem & { courseId?: string; courseTitle?: string })[] = [];
    for (const c of courses) {
      for (const acc of c.accomplishments_preview ?? []) {
        items.push({ ...acc, courseId: c.id, courseTitle: c.title });
      }
    }
    if (items.length === 0 && progress?.accomplishments) {
      return progress.accomplishments.map((item) => ({
        ...item,
        courseId: progress.course_id,
        courseTitle: progress.title,
      }));
    }
    return items;
  }, [bannerScope, courses, progress]);

  const opportunitiesList = useMemo((): (KcOpportunityItem & { courseId?: string; courseTitle?: string })[] => {
    if (bannerScope === "selected_course" && progress) {
      return (progress.opportunities ?? []).map((item) => ({
        ...item,
        courseId: progress.course_id,
        courseTitle: progress.title,
      }));
    }
    const items: (KcOpportunityItem & { courseId?: string; courseTitle?: string })[] = [];
    for (const c of courses) {
      for (const opp of c.opportunities_preview ?? []) {
        items.push({ ...opp, courseId: c.id, courseTitle: c.title });
      }
    }
    if (items.length === 0 && progress?.opportunities) {
      return progress.opportunities.map((item) => ({
        ...item,
        courseId: progress.course_id,
        courseTitle: progress.title,
      }));
    }
    return items;
  }, [bannerScope, courses, progress]);

  const sortedCourses = useMemo(() => {
    const copy = [...courses];
    copy.sort((a, b) => {
      const aActive = (a.in_progress_count ?? 0) > 0 ? 2 : (a.completed_count ?? 0) > 0 ? 1 : 0;
      const bActive = (b.in_progress_count ?? 0) > 0 ? 2 : (b.completed_count ?? 0) > 0 ? 1 : 0;
      if (aActive !== bActive) return bActive - aActive;
      return a.title.localeCompare(b.title);
    });
    if (courseFilter === "active_completed") {
      const filtered = copy.filter(
        (c) => (c.completed_count ?? 0) > 0 || (c.in_progress_count ?? 0) > 0 || c.id === courseId,
      );
      return filtered.length > 0 ? filtered : copy;
    }
    return copy;
  }, [courses, courseFilter, courseId]);

  const groups = progress ? unitsByStatus(progress.units) : null;
  const show = Boolean(studentId && courseId && progress && network && groups);
  const score = progress ? courseScore(progress.units, progress.known) : null;

  const rosterCounts = useMemo(() => {
    const units = progress?.units ?? [];
    return {
      all: units.length,
      known: units.filter((u) => unitDisplayStatus(u) === "known").length,
      fragile: units.filter((u) => unitDisplayStatus(u) === "fragile").length,
      in_progress: units.filter((u) => unitDisplayStatus(u) === "in_progress").length,
      not_started: units.filter((u) => unitDisplayStatus(u) === "not_started").length,
    };
  }, [progress]);

  const filteredRoster = useMemo(() => {
    const units = progress?.units ?? [];
    const q = rosterQuery.trim().toLowerCase();
    return units.filter((u) => {
      if (rosterFilter !== "all" && unitDisplayStatus(u) !== rosterFilter) return false;
      if (!q) return true;
      return (
        u.title.toLowerCase().includes(q) ||
        u.code.toLowerCase().includes(q) ||
        (u.summary ?? "").toLowerCase().includes(q)
      );
    });
  }, [progress, rosterFilter, rosterQuery]);

  const selectedUnit = useMemo(() => {
    if (!progress) return null;
    if (selectedCode) {
      const found = progress.units.find((u) => u.code === selectedCode);
      if (found) return found;
    }
    return defaultSelectedUnit(progress.units);
  }, [progress, selectedCode]);

  function selectComponentByCode(code: string) {
    setSelectedCode(code);
  }

  const cp = activeLearner?.child_profile;
  const gradeBandText = optionLabel(GRADE_BAND_OPTIONS, activeLearner?.grade_band ?? cp?.grade_band);
  const explanationText = optionLabel(
    EXPLANATION_STYLE_OPTIONS,
    activeLearner?.explanation_style ?? cp?.explanation_style,
  );
  const appetiteText = optionLabel(
    CHALLENGE_APPETITE_OPTIONS,
    activeLearner?.challenge_appetite ?? cp?.challenge_appetite,
  );
  const interestTags = activeLearner?.interest_tags ?? cp?.interest_tags ?? [];

  return (
    <main className="ds-shell kc-screen kc-progress kc-progress-overhaul">
      <KcBanner name="KC Course Progress" />
      <section className="kc-progress-body">
        {error ? (
          <div className="banner" role="alert">
            <p>{error}</p>
          </div>
        ) : null}

        {/* SECTION 1: Learner Header & Portfolio Rollup Bar */}
        <section className="kc-dash-header" aria-label="Learner Header and Portfolio Rollup">
          <div className="kc-dash-learner-top">
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

            {activeLearner ? (
              <div className="kc-learner-badges" aria-label="Learner Layer 2 profile snapshot">
                <span className="kc-profile-pill">
                  <strong>{activeLearner.display_name}</strong>
                  {activeLearner.age != null ? ` · Age ${activeLearner.age}` : ""}
                </span>
                {gradeBandText ? <span className="kc-profile-pill">{gradeBandText}</span> : null}
                {explanationText ? <span className="kc-profile-pill">Style: {explanationText}</span> : null}
                {appetiteText ? <span className="kc-profile-pill">Pace: {appetiteText}</span> : null}
                {interestTags.map((tag) => (
                  <span key={tag} className="kc-profile-pill is-interest">
                    {optionLabel(INTEREST_TAG_OPTIONS, tag)}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <div className="kc-kpi-grid" role="region" aria-label="Portfolio KPIs">
            <div className="kc-kpi-card">
              <span className="kc-kpi-label">Courses Active &amp; Completed</span>
              <strong className="kc-kpi-value">
                {portfolioStats.completedCourses} Completed · {portfolioStats.inProgressCourses} In Progress
              </strong>
              <span className="kc-kpi-sub">{courses.length} ready courses in catalog</span>
            </div>
            <div className="kc-kpi-card is-known">
              <span className="kc-kpi-label">Mastered Components (Known)</span>
              <strong className="kc-kpi-value">{portfolioStats.knownTotal}</strong>
              <span className="kc-kpi-sub">Every counting block passed without reveal</span>
            </div>
            <div className="kc-kpi-card is-fragile">
              <span className="kc-kpi-label">Completed with Gaps (Fragile)</span>
              <strong className="kc-kpi-value">{portfolioStats.fragileTotal}</strong>
              <span className="kc-kpi-sub">Finished with at least one revealed block</span>
            </div>
            <div className="kc-kpi-card is-accuracy">
              <span className="kc-kpi-label">First-Try Block Accuracy</span>
              <strong className="kc-kpi-value">{portfolioStats.accuracyPct}%</strong>
              <span className="kc-kpi-sub">
                {portfolioStats.firstTryBlocksTotal} / {portfolioStats.completedBlocksTotal} completed blocks on 1st try
              </span>
            </div>
          </div>
        </section>

        {/* SECTION 2: Key Learning Accomplishments & Opportunities Banner */}
        <section
          className="kc-insights-banner"
          aria-label="Key Learning Accomplishments and Opportunities"
        >
          <header className="kc-insights-header">
            <div>
              <h2>Key Learning Accomplishments &amp; Opportunities</h2>
              <p className="ds-quiet">
                Synthesized from captured AI session closes, first-try block passes, revealed blocks, and prerequisite
                readiness.
              </p>
            </div>
            <div className="kc-scope-pills" role="group" aria-label="Insights scope">
              <button
                type="button"
                className={`kc-chip${bannerScope === "selected_course" ? " is-active" : ""}`}
                aria-pressed={bannerScope === "selected_course"}
                onClick={() => setBannerScope("selected_course")}
              >
                Selected Course
              </button>
              <button
                type="button"
                className={`kc-chip${bannerScope === "all_courses" ? " is-active" : ""}`}
                aria-pressed={bannerScope === "all_courses"}
                onClick={() => setBannerScope("all_courses")}
              >
                All Active Courses
              </button>
            </div>
          </header>

          <div className="kc-insights-columns">
            <div className="kc-insight-card is-accomplishments" aria-label="Key Learning Accomplishments">
              <h3>Key Learning Accomplishments</h3>
              {accomplishmentsList.length === 0 ? (
                <p className="ds-quiet">
                  Complete blocks and components in the AI Tutor to populate mastered concepts and strengths.
                </p>
              ) : (
                <ul className="kc-insight-list">
                  {accomplishmentsList.map((item, idx) => (
                    <li key={`${item.component_code}-${item.kind}-${idx}`}>
                      <div className="kc-insight-top">
                        <button
                          type="button"
                          className="kc-comp-badge is-known"
                          onClick={() => {
                            if (item.courseId && item.courseId !== courseId) {
                              visit(studentId, item.courseId);
                            } else {
                              selectComponentByCode(item.component_code);
                            }
                          }}
                        >
                          {item.component_title}
                        </button>
                        <span className="kc-insight-kind">{item.kind.replace(/_/g, " ")}</span>
                      </div>
                      <p className="kc-insight-summary">{item.summary}</p>
                      {item.detail ? <p className="kc-insight-detail">{item.detail}</p> : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="kc-insight-card is-opportunities" aria-label="Learning Opportunities and Next Steps">
              <h3>Learning Opportunities &amp; Next Steps</h3>
              {opportunitiesList.length === 0 ? (
                <p className="ds-quiet">
                  No fragile gaps or misconceptions recorded. Pick any component below to start or continue practice.
                </p>
              ) : (
                <ul className="kc-insight-list">
                  {opportunitiesList.map((item, idx) => {
                    const targetCourseId = item.courseId || courseId;
                    return (
                      <li key={`${item.component_code}-${item.kind}-${idx}`}>
                        <div className="kc-insight-top">
                          <span className="kc-comp-badge is-fragile">{item.component_title}</span>
                          <span className="kc-insight-kind">{item.kind.replace(/_/g, " ")}</span>
                        </div>
                        <p className="kc-insight-summary">{item.summary}</p>
                        {item.detail ? <p className="kc-insight-detail">{item.detail}</p> : null}
                        <div className="kc-insight-actions">
                          <button
                            type="button"
                            className="ghost kc-mini-btn"
                            onClick={() => {
                              if (targetCourseId && targetCourseId !== courseId) {
                                visit(studentId, targetCourseId);
                              } else {
                                selectComponentByCode(item.component_code);
                              }
                            }}
                          >
                            Inspect Component
                          </button>
                          <a
                            className="button kc-mini-btn"
                            href={tutorComponentHref(studentId, targetCourseId, item.component_id)}
                          >
                            Practice in AI Tutor
                          </a>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
        </section>

        {/* SECTION 3: Interactive Course Portfolio Tiles */}
        <section className="kc-portfolio-section" aria-label="Course Portfolio">
          <header className="kc-portfolio-header">
            <div>
              <h2>Course Portfolio</h2>
              <p className="ds-quiet">Select any course tile to explore its prerequisite map and component inspector.</p>
            </div>
            <div className="kc-scope-pills" role="group" aria-label="Course portfolio filter">
              <button
                type="button"
                className={`kc-chip${courseFilter === "active_completed" ? " is-active" : ""}`}
                aria-pressed={courseFilter === "active_completed"}
                onClick={() => setCourseFilter("active_completed")}
              >
                Active &amp; Completed
              </button>
              <button
                type="button"
                className={`kc-chip${courseFilter === "all" ? " is-active" : ""}`}
                aria-pressed={courseFilter === "all"}
                onClick={() => setCourseFilter("all")}
              >
                All Courses ({courses.length})
              </button>
            </div>
          </header>

          <div className="kc-course-tiles">
            {sortedCourses.map((c) => {
              const isSelected = c.id === courseId;
              const totalComp = Math.max(c.component_count ?? 0, 1);
              const knownCnt = c.known_count ?? 0;
              const fragileCnt = c.fragile_count ?? 0;
              const inProgCnt = c.in_progress_count ?? 0;
              const completedCnt = c.completed_count ?? knownCnt + fragileCnt;
              const pct = c.percent ?? Math.round((completedCnt * 100) / totalComp);
              const knownW = Math.round((knownCnt * 100) / totalComp);
              const fragileW = Math.round((fragileCnt * 100) / totalComp);
              const inProgW = Math.round((inProgCnt * 100) / totalComp);

              return (
                <div
                  key={c.id}
                  role="button"
                  tabIndex={0}
                  className={`kc-course-tile${isSelected ? " is-selected" : ""}`}
                  aria-pressed={isSelected}
                  onClick={() => {
                    setCourse(c.id);
                    visit(studentId, c.id);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setCourse(c.id);
                      visit(studentId, c.id);
                    }
                  }}
                >
                  <div className="kc-tile-top">
                    <div>
                      <h3>{c.title}</h3>
                      <span className="kc-tile-code">{c.code}</span>
                    </div>
                    <div className="kc-tile-badges">
                      <span className="kc-badge">{kindLabel(c.kind)}</span>
                      <span className="kc-badge">Ages {c.audience}</span>
                      <span className={`kc-badge ${c.unlocked === false ? "is-locked" : "is-unlocked"}`}>
                        {c.unlocked === false ? "Locked" : "Unlocked"}
                      </span>
                    </div>
                  </div>

                  <div className="kc-stacked-bar-row">
                    <div className="kc-stacked-bar" aria-label={`${c.title} mastery breakdown`}>
                      <span className="seg-known" style={{ width: `${knownW}%` }} title={`Known: ${knownCnt}`} />
                      <span className="seg-fragile" style={{ width: `${fragileW}%` }} title={`Fragile: ${fragileCnt}`} />
                      <span
                        className="seg-in-progress"
                        style={{ width: `${inProgW}%` }}
                        title={`In Progress: ${inProgCnt}`}
                      />
                    </div>
                    <strong className="kc-tile-pct">{pct}%</strong>
                  </div>

                  <p className="kc-tile-counts">
                    {completedCnt}/{c.component_count ?? 0} Completed ({knownCnt} Known · {fragileCnt} Fragile) ·{" "}
                    {inProgCnt} In Progress
                  </p>
                  <div className="kc-tile-foot">
                    <span>
                      {c.completed_blocks_count ?? 0}/{c.total_blocks_count ?? 0} Blocks Completed
                    </span>
                    <span>{formatTimestamp(c.last_active_at)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* SECTION 4: Selected Course Deep-Dive Workspace */}
        {show && progress && network && groups ? (
          <section className="kc-workspace" aria-label={`${progress.title} Deep-Dive Workspace`}>
            <header className="kc-workspace-header">
              <div className="kc-workspace-title-block">
                <div className="kc-workspace-title-row">
                  <h2>{progress.title}</h2>
                  <span className={`kc-status-pill is-${courseOverallStatus(progress).tone}`}>
                    {courseOverallStatus(progress).label}
                  </span>
                  <span className="kc-badge">{kindLabel(progress.kind)}</span>
                  {progress.minutes ? <span className="kc-badge">{progress.minutes} min target</span> : null}
                </div>
                {progress.description ? <p className="kc-workspace-desc">{progress.description}</p> : null}
                <p className="kc-scoring-legend">
                  <strong>Scoring rule:</strong> <em>Known</em> means every counting block passed without reveal.{" "}
                  <em>Fragile</em> means the component is finished, but at least one counting block was revealed after
                  max retries. Curiosity blocks count only when configured.
                </p>
              </div>

              <div className="kc-workspace-score-box">
                <p className="kc-progress-score">
                  <strong>{score?.percent ?? progress.percent}%</strong>
                  <span>{score ? `${score.finished} of ${score.total}` : progress.count_label}</span>
                </p>
                <p className="kc-progress-known">{progress.known} known</p>
                <a
                  className="button"
                  href={tutorComponentHref(
                    studentId,
                    courseId,
                    selectedUnit?.id ?? progress.units[0]?.id ?? "",
                  )}
                >
                  Continue Course in AI Tutor
                </a>
              </div>
            </header>

            <div className="kc-workspace-split">
              {/* Left Column: Clickable Network Diagram + Filterable Roster */}
              <div className="kc-workspace-left">
                <section className="kc-progress-map" aria-label={`${progress.title} network`}>
                  <div className="kc-map-header">
                    <div>
                      <h3>Interactive Prerequisite Network</h3>
                      <p className="ds-quiet">
                        Click any component node to highlight its prerequisite chain and inspect its rubric &amp; blocks.
                      </p>
                    </div>
                    <ul className="kc-progress-legend">
                      <li>
                        <span className="kc-progress-swatch is-completed" />
                        Known
                      </li>
                      <li>
                        <span className="kc-progress-swatch is-fragile" />
                        Fragile
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
                  </div>
                  <NetworkFrame
                    network={network}
                    statusByCode={statusByCode(progress.units)}
                    noteByCode={masteryByCode(progress.units)}
                    selectedCode={selectedUnit?.code ?? null}
                    onSelectNode={selectComponentByCode}
                    resetKey={`${studentId}:${courseId}`}
                  />
                </section>

                <section className="kc-roster-section" aria-label="Component Roster">
                  <div className="kc-roster-controls">
                    <div className="kc-roster-tabs" role="group" aria-label="Filter components by status">
                      {(
                        [
                          ["all", `All (${rosterCounts.all})`],
                          ["known", `Known (${rosterCounts.known})`],
                          ["fragile", `Fragile (${rosterCounts.fragile})`],
                          ["in_progress", `In Progress (${rosterCounts.in_progress})`],
                          ["not_started", `Not Started (${rosterCounts.not_started})`],
                        ] as const
                      ).map(([id, label]) => (
                        <button
                          key={id}
                          type="button"
                          className={`kc-chip${rosterFilter === id ? " is-active" : ""}`}
                          aria-pressed={rosterFilter === id}
                          onClick={() => setRosterFilter(id)}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    <input
                      type="search"
                      className="kc-roster-search"
                      aria-label="Search components"
                      placeholder="Filter components by title or code..."
                      value={rosterQuery}
                      onChange={(e) => setRosterQuery(e.target.value)}
                    />
                  </div>

                  <ul className="kc-roster-list">
                    {filteredRoster.map((unit) => {
                      const stepIndex = progress.units.findIndex((u) => u.id === unit.id) + 1;
                      const isSel = selectedUnit?.code === unit.code;
                      const ds = unitDisplayStatus(unit);
                      const doneB = unit.completed_blocks ?? unit.finished_blocks ?? 0;
                      const totalB = Math.max(unit.total_blocks ?? 1, 1);
                      const blockPct = Math.round((doneB * 100) / totalB);
                      return (
                        <li key={unit.id}>
                          <button
                            type="button"
                            className={`kc-roster-row${isSel ? " is-selected" : ""}`}
                            aria-pressed={isSel}
                            onClick={() => selectComponentByCode(unit.code)}
                          >
                            <div className="kc-roster-row-main">
                              <span className="kc-step-num">{stepIndex}</span>
                              <div>
                                <strong>{unit.title}</strong>
                                <span className="kc-roster-code">
                                  {unit.code}
                                  {unit.patch ? " · patch" : ""}
                                </span>
                              </div>
                            </div>
                            <div className="kc-roster-row-meta">
                              <span className={`kc-status-pill is-${ds}`}>{unitBadgeText(unit)}</span>
                              <div className="kc-mini-bar-wrap">
                                <div className="kc-mini-bar">
                                  <span className={`is-${ds}`} style={{ width: `${blockPct}%` }} />
                                </div>
                                <span>
                                  {doneB}/{unit.total_blocks ?? 0} blocks
                                </span>
                              </div>
                              <span className="kc-roster-attempts">
                                {attemptLabel(unit.total_attempts ?? 0)}
                              </span>
                            </div>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </section>

                {/* Preserve status-grouped Completed / In progress / Not started summary lists + modal trigger */}
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
                              {list.status === "not_started" ? (
                                <div
                                  className="kc-not-started-item"
                                  onClick={() => selectComponentByCode(unit.code)}
                                >
                                  <strong>{unit.title}</strong>
                                  <span>{unitLine(unit)}</span>
                                </div>
                              ) : (
                                <button
                                  type="button"
                                  className="kc-progress-open"
                                  aria-haspopup="dialog"
                                  onClick={() => {
                                    selectComponentByCode(unit.code);
                                    setOpenUnit(unit);
                                  }}
                                >
                                  <strong>{unit.title}</strong>
                                  <span>{unitLine(unit)}</span>
                                </button>
                              )}
                            </li>
                          ))}
                        </ul>
                      </section>
                    );
                  })}
                </div>
              </div>

              {/* Right Column: Sticky Component Inspector Panel */}
              <aside className="kc-inspector" aria-label="Component Inspector">
                {selectedUnit ? (
                  <div className="kc-inspector-card">
                    <header className="kc-inspector-header">
                      <div>
                        <span className="kc-inspector-eyebrow">
                          Component Inspector · {selectedUnit.code}
                          {selectedUnit.patch ? " (Patch)" : ""}
                        </span>
                        <h3>{selectedUnit.title}</h3>
                      </div>
                      <div className="kc-inspector-badges">
                        <span className={`kc-status-pill is-${unitDisplayStatus(selectedUnit)}`}>
                          {unitBadgeText(selectedUnit)}
                        </span>
                        <span className="kc-badge">
                          p(known): {Math.round((selectedUnit.p_known ?? 0) * 100)}%
                        </span>
                        <span className="kc-badge">
                          {selectedUnit.completed_blocks ?? selectedUnit.finished_blocks ?? 0}/
                          {selectedUnit.total_blocks ?? 0} blocks
                        </span>
                        <span className="kc-badge">
                          {attemptLabel(selectedUnit.total_attempts ?? 0)}
                        </span>
                      </div>
                      <div className="kc-inspector-actions">
                        <a
                          className="button"
                          href={tutorComponentHref(studentId, courseId, selectedUnit.id)}
                        >
                          Open in AI Tutor
                        </a>
                        {selectedUnit.status !== "not_started" ? (
                          <button
                            type="button"
                            className="ghost"
                            onClick={() => setOpenUnit(selectedUnit)}
                          >
                            Quick Summary Modal
                          </button>
                        ) : null}
                      </div>
                      {selectedUnit.updated_at ? (
                        <p className="kc-inspector-time">
                          Last updated: {formatTimestamp(selectedUnit.updated_at)}
                        </p>
                      ) : null}
                    </header>

                    {/* 2. Score & Mastery Justification + Captured AI Close Summary */}
                    <section className="kc-inspector-section" aria-label="Score Justification and Close Feedback">
                      <h4>Score &amp; Mastery Justification</h4>
                      <p className="kc-justification-box">
                        {selectedUnit.score_justification ||
                          selectedUnit.result?.justification ||
                          "Complete the blocks in this component to record a mastery justification."}
                      </p>

                      <div className="kc-feedback-grid">
                        <div className="kc-feedback-card is-strong">
                          <strong>What Was Strong</strong>
                          <p>
                            {selectedUnit.what_was_strong ||
                              selectedUnit.result?.strong ||
                              "No strength synthesis stored yet."}
                          </p>
                        </div>
                        <div className="kc-feedback-card is-work-on">
                          <strong>Opportunities to Practice</strong>
                          <p>
                            {selectedUnit.what_to_work_on ||
                              selectedUnit.result?.work_on ||
                              "No practice gaps stored yet."}
                          </p>
                        </div>
                      </div>
                      {selectedUnit.close_text ? (
                        <p className="kc-close-quote">&ldquo;{selectedUnit.close_text}&rdquo;</p>
                      ) : null}
                    </section>

                    {/* 3. Derived Rubric & Block-by-Block Execution Timeline */}
                    <section className="kc-inspector-section" aria-label="Derived Rubric and Block Execution Timeline">
                      <h4>
                        Derived Rubric &amp; Block-by-Block Execution Timeline (
                        {selectedUnit.block_details?.length ?? selectedUnit.total_blocks ?? 0})
                      </h4>
                      {(selectedUnit.block_details ?? []).length > 0 ? (
                        <ol className="kc-block-timeline">
                          {(selectedUnit.block_details ?? []).map((blk) => {
                            const pill = blockOutcomePill(blk);
                            return (
                              <li key={blk.block_id} className={`kc-timeline-item ${pill.tone}`}>
                                <div className="kc-timeline-top">
                                  <span className="kc-timeline-step">Block {blk.index}</span>
                                  <span className="kc-badge">{blk.label}</span>
                                  <span className={`kc-badge ${blk.counts_toward_mastery ? "is-counting" : "is-exploratory"}`}>
                                    {blk.counts_toward_mastery ? "Counts toward mastery" : "Exploratory"}
                                  </span>
                                  <span className={`kc-status-pill ${pill.tone}`}>{pill.text}</span>
                                </div>
                                {blk.rubric_line ? (
                                  <p className="kc-timeline-rubric">
                                    <strong>Rubric:</strong> {blk.rubric_line}
                                  </p>
                                ) : null}
                                {blk.prompt_preview && blk.prompt_preview !== blk.rubric_line ? (
                                  <p className="kc-timeline-preview">{blk.prompt_preview}</p>
                                ) : null}
                                <div className="kc-timeline-meta">
                                  <span>
                                    Attempts: {blk.attempts}
                                    {blk.max_retries != null ? ` / max ${blk.max_retries} retries` : ""}
                                  </span>
                                  {blk.eliminated_choices.length > 0 ? (
                                    <span>Eliminated choices: {blk.eliminated_choices.join(", ")}</span>
                                  ) : null}
                                </div>
                              </li>
                            );
                          })}
                        </ol>
                      ) : (
                        <ul className="kc-rubric-fallback">
                          {(selectedUnit.rubric ?? []).map((line, idx) => (
                            <li key={idx}>{line}</li>
                          ))}
                        </ul>
                      )}
                    </section>

                    {/* 4. Core Truth, Misconceptions & Prerequisite Graph Links */}
                    <section className="kc-inspector-section" aria-label="Core Truth and Graph Links">
                      <h4>Core Truth, Misconceptions &amp; Graph Links</h4>
                      {selectedUnit.core_truth ? (
                        <p className="kc-core-truth">
                          <strong>Core Truth:</strong> {selectedUnit.core_truth}
                        </p>
                      ) : null}
                      {selectedUnit.outline ? (
                        <p className="kc-outline-text">
                          <strong>Outline:</strong> {selectedUnit.outline}
                        </p>
                      ) : null}

                      {(selectedUnit.student_misconceptions ?? []).length > 0 ? (
                        <div className="kc-misc-box is-captured">
                          <strong>Captured Learner Misconceptions:</strong>
                          <ul>
                            {(selectedUnit.student_misconceptions ?? []).map((m, idx) => (
                              <li key={idx}>{m}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}

                      {(selectedUnit.misconceptions ?? []).length > 0 ? (
                        <div className="kc-misc-box">
                          <strong>Authored Traps to Watch For:</strong>
                          <ul>
                            {(selectedUnit.misconceptions ?? []).map((m, idx) => (
                              <li key={idx}>
                                {m.wrong_move}
                                {m.broken_kc ? ` (→ ${m.broken_kc})` : ""}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}

                      <div className="kc-graph-links">
                        <div>
                          <strong>Prerequisites:</strong>
                          {(selectedUnit.prerequisite_codes ?? []).length === 0 ? (
                            <span className="ds-quiet"> None (entry component)</span>
                          ) : (
                            <div className="kc-link-pills">
                              {(selectedUnit.prerequisite_codes ?? []).map((pcode) => {
                                const target = progress.units.find((u) => u.code === pcode);
                                return (
                                  <button
                                    key={pcode}
                                    type="button"
                                    className="kc-chip"
                                    onClick={() => selectComponentByCode(pcode)}
                                  >
                                    ← {target ? target.title : pcode}
                                  </button>
                                );
                              })}
                            </div>
                          )}
                        </div>
                        <div>
                          <strong>Unlocks / Dependents:</strong>
                          {(selectedUnit.dependent_codes ?? []).length === 0 ? (
                            <span className="ds-quiet"> None (terminal component)</span>
                          ) : (
                            <div className="kc-link-pills">
                              {(selectedUnit.dependent_codes ?? []).map((dcode) => {
                                const target = progress.units.find((u) => u.code === dcode);
                                return (
                                  <button
                                    key={dcode}
                                    type="button"
                                    className="kc-chip"
                                    onClick={() => selectComponentByCode(dcode)}
                                  >
                                    {target ? target.title : dcode} →
                                  </button>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      </div>
                    </section>
                  </div>
                ) : (
                  <p className="ds-quiet">Select a component from the map or roster to inspect its details.</p>
                )}
              </aside>
            </div>
          </section>
        ) : null}
        {openUnit ? <ComponentPopup unit={openUnit} onClose={() => setOpenUnit(null)} /> : null}
      </section>
    </main>
  );
}
