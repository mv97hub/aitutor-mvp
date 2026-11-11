import { KcCourseProgress } from "@/components/KcCourseProgress";
import { ParentFrame } from "@/components/parent/ParentFrame";
import { ParentMissing } from "@/components/parent/ParentMissing";
import { api } from "@/lib/api";
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
  let courses: KcTutorCourse[] = [];
  let courseId = knownId(query.course) ?? "";
  let progress: KcProgress | null = null;
  let network: KcNetwork | null = null;
  let error: string | null = null;
  const base = `/parents/${parentId}/children/${studentId}`;

  try {
    const [loaded, linked] = await Promise.all([
      api<Parent>(`/parents/${parentId}`),
      api<Student[]>(`/parents/${parentId}/students`),
    ]);
    parent = loaded;
    learner = linked.find((item) => item.id === studentId) ?? null;
    if (learner) {
      courses = coursesStartedFirst(await api<KcTutorCourse[]>(`${base}/courses`));
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
  }

  return (
    <ParentFrame parentId={parent.id} parentName={parent.name} studentId={learner.id} current="progress">
      <KcCourseProgress
        studentId={learner.id}
        studentName={learner.display_name}
        courses={courses}
        courseId={courseId}
        progress={progress}
        network={network}
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
