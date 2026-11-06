import { KcTutor } from "@/components/KcTutor";
import { api } from "@/lib/api";
import type { KcProgress, KcTutorCourse, KcTutorSession } from "@/lib/kc";
import type { Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "KC Tutor · AI Tutor" };

export default async function KcTutorPage({
  searchParams,
}: {
  searchParams: Promise<{ student?: string; course?: string; kc?: string; session?: string; error?: string }>;
}) {
  const params = await searchParams;
  let students: Student[] = [];
  let courses: KcTutorCourse[] = [];
  let progress: KcProgress | null = null;
  let session: KcTutorSession | null = null;
  let error: string | null = params.error ? decodeURIComponent(params.error) : null;
  try {
    [students, courses] = await Promise.all([api<Student[]>("/students"), api<KcTutorCourse[]>("/kc/tutor/courses")]);
    if (params.student && params.course) {
      progress = await api<KcProgress>(`/kc/tutor/courses/${params.course}?student_id=${params.student}`);
    }
    if (params.session) {
      session = await api<KcTutorSession>(`/kc/tutor/sessions/${params.session}`);
    } else if (params.student && params.course && params.kc) {
      session = await api<KcTutorSession>("/kc/tutor/sessions", {
        method: "POST",
        body: JSON.stringify({ student_id: params.student, course_id: params.course, kc_id: params.kc }),
      });
    }
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return (
    <KcTutor
      students={students}
      courses={courses}
      studentId={params.student ?? ""}
      courseId={params.course ?? ""}
      progress={progress}
      session={session}
      error={error}
    />
  );
}
