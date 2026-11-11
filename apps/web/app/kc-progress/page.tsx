import { redirect } from "next/navigation";

import { KcCourseProgress } from "@/components/KcCourseProgress";
import { api } from "@/lib/api";
import type { KcNetwork, KcProgress, KcTutorCourse } from "@/lib/kc";
import { coursesStartedFirst, portfolioCourseStatus } from "@/lib/kc-progress";
import type { Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Detailed Progress · AI Tutor" };

export default async function KcProgressPage({
  searchParams,
}: {
  searchParams: Promise<{ student?: string; course?: string }>;
}) {
  const params = await searchParams;
  const studentId = params.student?.trim() ?? "";
  if (!studentId) redirect("/learn");

  let studentName = "";
  let courses: KcTutorCourse[] = [];
  let courseId = params.course?.trim() ?? "";
  let progress: KcProgress | null = null;
  let network: KcNetwork | null = null;
  let error: string | null = null;

  try {
    const students = await api<Student[]>("/students");
    studentName = students.find((student) => student.id === studentId)?.display_name ?? "";
  } catch {
    studentName = "";
  }

  try {
    const loaded = await api<KcTutorCourse[]>(
      `/kc/tutor/courses?student_id=${encodeURIComponent(studentId)}`,
    );
    courses = coursesStartedFirst(loaded);
    if (!params.course?.trim()) {
      const started = courses.find((course) => portfolioCourseStatus(course) !== "");
      courseId = (started ?? courses[0])?.id ?? "";
    }
  } catch (err) {
    error = err instanceof Error ? err.message : "The progress service is not reachable.";
  }

  if (courseId) {
    try {
      progress = await api<KcProgress>(
        `/kc/tutor/courses/${encodeURIComponent(courseId)}?student_id=${encodeURIComponent(studentId)}`,
      );
    } catch (err) {
      error = err instanceof Error ? err.message : "The progress service is not reachable.";
      progress = null;
    }
    try {
      network = await api<KcNetwork>(`/kc/courses/${encodeURIComponent(courseId)}/network`);
    } catch {
      network = null;
    }
  }

  return (
    <KcCourseProgress
      studentId={studentId}
      studentName={studentName}
      courses={courses}
      courseId={courseId}
      progress={progress}
      network={network}
      error={error}
    />
  );
}
