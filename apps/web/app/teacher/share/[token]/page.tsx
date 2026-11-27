import { SkillRadar } from "@/components/progress/SkillRadar";
import { api } from "@/lib/api";
import {
  BIOMARKER_LABELS,
  formatHakeGain,
  formatPercent,
  trajectoryTone,
  type TeacherSnapshot,
} from "@/lib/parent-copilot";

export const dynamic = "force-dynamic";

export const metadata = { title: "Teacher Snapshot · Read-only Progress · AI Tutor" };

export default async function TeacherSharePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  let snapshot: TeacherSnapshot | null = null;
  let error: string | null = null;

  try {
    snapshot = await api<TeacherSnapshot>(`/teacher/share/${encodeURIComponent(token)}`);
  } catch (err) {
    error = err instanceof Error ? err.message : "This teacher share link is invalid or has been revoked.";
  }

  if (!snapshot) {
    return (
      <main className="teacher-share-page">
        <div className="teacher-share-card">
          <h1>Snapshot Unavailable</h1>
          <p className="learn-quiet">{error || "This link may have expired or been revoked by the parent."}</p>
        </div>
      </main>
    );
  }

  const tone = trajectoryTone(snapshot.trajectory_state);

  return (
    <main className="teacher-share-page">
      <header className="teacher-share-header">
        <div>
          <p className="teacher-share-eyebrow">Read-Only Teacher Progress Snapshot</p>
          <h1>
            {snapshot.learner.first_name}
            {snapshot.learner.grade_band ? ` · ${snapshot.learner.grade_band.replace(/_/g, " ")}` : ""}
          </h1>
          <p className="learn-quiet">
            {snapshot.share_label} · No chat transcripts included · Shared by parent
          </p>
        </div>
        <span className={`copilot-badge is-${tone}`}>{snapshot.trajectory_meta.label}</span>
      </header>

      <section className="teacher-share-card">
        <h2>Learning Biomarkers</h2>
        <p className="learn-quiet">{snapshot.trajectory_meta.description}</p>
        <div className="copilot-bio-grid">
          {BIOMARKER_LABELS.map((item) => (
            <div key={item.key} className="copilot-bio-tile">
              <strong>{snapshot.biomarkers[item.key] ?? 0}</strong>
              <span>{item.label}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="teacher-share-card">
        <SkillRadar radar={snapshot.radar} heading={`${snapshot.learner.first_name} · Eight Thinking Skills`} />
      </section>

      <section className="teacher-share-card">
        <h2>Course Mastery, Standards & Blind Pre/Post Gain</h2>
        {snapshot.courses.length === 0 ? (
          <p className="learn-quiet">No course records available for this snapshot yet.</p>
        ) : (
          <div className="teacher-course-list">
            {snapshot.courses.map((course) => (
              <article key={course.course_id} className="teacher-course-item">
                <div className="copilot-card-head">
                  <div>
                    <h3>{course.title}</h3>
                    <p className="learn-quiet">
                      Known: {course.known_count}/{course.total_components} · Fragile: {course.fragile_count} · Blind
                      Pre → Post: {formatPercent(course.blind_exam.latest_pre_score)} →{" "}
                      {formatPercent(course.blind_exam.latest_post_score)} (Hake{" "}
                      {formatHakeGain(course.blind_exam.hake_g)})
                    </p>
                  </div>
                </div>
                {course.standards.length > 0 ? (
                  <p className="learn-quiet">
                    <strong>Standards:</strong> {course.standards.join(", ")}
                  </p>
                ) : null}
                {course.known_topics.length > 0 ? (
                  <p>
                    <strong>Mastered topics:</strong> {course.known_topics.join(", ")}
                  </p>
                ) : null}
                {course.fragile_topics.length > 0 ? (
                  <p>
                    <strong>Topics needing reinforcement:</strong> {course.fragile_topics.join(", ")}
                  </p>
                ) : null}
                {course.active_misconceptions.length > 0 ? (
                  <div className="copilot-misc-box">
                    <strong>Active misconceptions observed:</strong>
                    <ul>
                      {course.active_misconceptions.map((m, idx) => (
                        <li key={idx}>{m}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
