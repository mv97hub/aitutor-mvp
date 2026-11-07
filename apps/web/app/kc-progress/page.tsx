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
  const studentId = params.student ?? "";
  const courseId = params.course ?? "";
  let students: Student[] = [];
  let courses: KcTutorCourse[] = [];
  let progress: KcProgress | null = null;
  let network: KcNetwork | null = null;
  let error: string | null = null;
  try {
    [students, courses] = await Promise.all([api<Student[]>("/students"), api<KcTutorCourse[]>("/kc/tutor/courses")]);
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
