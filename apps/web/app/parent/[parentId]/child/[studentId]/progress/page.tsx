import { KcCourseProgress } from "@/components/KcCourseProgress";
import { ParentFrame } from "@/components/parent/ParentFrame";
import { ParentMissing } from "@/components/parent/ParentMissing";
import { api } from "@/lib/api";
import type { CourseExamSummary } from "@/lib/blind-exam";
import type { SkillRadarPayload } from "@/lib/graph2";
import type { KcNetwork, KcProgress, KcTutorCourse } from "@/lib/kc";
import { coursesStartedFirst, portfolioCourseStatus } from "@/lib/kc-progress";
import { knownId, parentHome, parentProgress, type Parent } from "@/lib/parent";
import type { Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Detailed Progress · Parent portal · AI Tutor" };

export default async function ParentProgressPage({
  params,
  searchParams,
}: {
  params: Promise<{ parentId: string; studentId: string }>;
  searchParams: Promise<{ course?: string }>;
}) {
  const { parentId: rawParent, studentId: rawStudent } = await params;
  const query = await searchParams;
  const parentId = knownId(rawParent);
  const studentId = knownId(rawStudent);
  if (!parentId || !studentId) {
    return <ParentMissing title="That page was not found." detail="Pick a parent and a child from the list." />;
  }

  let parent: Parent | null = null;
  let learner: Student | null = null;
  let learners: Student[] = [];
  let courses: KcTutorCourse[] = [];
  let courseId = knownId(query.course) ?? "";
  let progress: KcProgress | null = null;
  let network: KcNetwork | null = null;
  let radar: SkillRadarPayload | null = null;
  let examSummary: CourseExamSummary | null = null;
  let error: string | null = null;
  const base = `/parents/${parentId}/children/${studentId}`;

  try {
    const [loaded, linked] = await Promise.all([
      api<Parent>(`/parents/${parentId}`),
      api<Student[]>(`/parents/${parentId}/students`),
    ]);
    parent = loaded;
    learners = linked;
    learner = linked.find((item) => item.id === studentId) ?? null;
    if (learner) {
      const [loadedCourses, loadedRadar] = await Promise.all([
        api<KcTutorCourse[]>(`${base}/courses`),
        api<SkillRadarPayload>(`${base}/radar`).catch(() => null),
      ]);
      courses = coursesStartedFirst(loadedCourses);
      radar = loadedRadar;
      if (!courseId) {
        const started = courses.find((course) => portfolioCourseStatus(course) !== "");
        courseId = (started ?? courses[0])?.id ?? "";
      }
    }
  } catch (err) {
    error = err instanceof Error ? err.message : "The progress service is not reachable.";
  }
  if (!parent) {
    return <ParentMissing title="That parent was not found." detail={error || "Pick someone from the parent list."} />;
  }
  if (!learner) {
    return <ParentMissing title="That child is not linked to you." detail={error || "Choose your children in settings."} />;
  }

  if (courseId) {
    try {
      progress = await api<KcProgress>(`${base}/courses/${encodeURIComponent(courseId)}/progress`);
    } catch (err) {
      error = err instanceof Error ? err.message : "The progress service is not reachable.";
    }
    try {
      network = await api<KcNetwork>(`${base}/courses/${encodeURIComponent(courseId)}/network`);
    } catch {
      network = null;
    }
    examSummary = await api<CourseExamSummary>(
      `${base}/courses/${encodeURIComponent(courseId)}/exam`,
    ).catch(() => null);
  }

  return (
    <ParentFrame parentId={parent.id} parentName={parent.name} studentId={learner.id} learners={learners} current="progress">
      <KcCourseProgress
        studentId={learner.id}
        studentName={learner.display_name}
        courses={courses}
        courseId={courseId}
        progress={progress}
        network={network}
        radar={radar}
        examSummary={examSummary}
        error={error}
        area={{
          backHref: parentHome(parent.id),
          backLabel: "Back to dashboard",
          progressPath: parentProgress(parent.id, learner.id),
        }}
      />
    </ParentFrame>
  );
}
