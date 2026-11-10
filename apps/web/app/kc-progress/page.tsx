import { KcCourseProgress } from "@/components/KcCourseProgress";
import { api } from "@/lib/api";
import type { KcNetwork, KcProgress, KcTutorCourse } from "@/lib/kc";
import type { Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "KC Course Progress · AI Tutor" };

export default async function KcProgressPage({
  searchParams,
}: {
  searchParams: Promise<{ student?: string; course?: string }>;
}) {
  const params = await searchParams;
  let studentId = params.student ?? "";
  let courseId = params.course ?? "";
  let students: Student[] = [];
  let courses: KcTutorCourse[] = [];
  let progress: KcProgress | null = null;
  let network: KcNetwork | null = null;
  let error: string | null = null;
  try {
    students = await api<Student[]>("/students");
    if (!studentId && students.length > 0) {
      studentId = students[0].id;
    }
    const courseQuery = studentId ? `?student_id=${encodeURIComponent(studentId)}` : "";
    courses = await api<KcTutorCourse[]>(`/kc/tutor/courses${courseQuery}`);
    if (!courseId && courses.length > 0) {
      const activeOrDone = courses.find(
        (c) => (c.completed_count ?? 0) > 0 || (c.in_progress_count ?? 0) > 0,
      );
      courseId = (activeOrDone ?? courses[0]).id;
    }
    if (studentId && courseId) {
      [progress, network] = await Promise.all([
        api<KcProgress>(`/kc/tutor/courses/${courseId}?student_id=${studentId}`),
        api<KcNetwork>(`/kc/courses/${courseId}/network`),
      ]);
    }
  } catch (err) {
    error = err instanceof Error ? err.message : "The progress service is not reachable.";
    progress = null;
    network = null;
  }
  return (
    <KcCourseProgress
      students={students}
      courses={courses}
      studentId={studentId}
      courseId={courseId}
      progress={progress}
      network={network}
      error={error}
    />
  );
}
