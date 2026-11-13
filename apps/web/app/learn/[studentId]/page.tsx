import { Button, Crayon } from "@/components/crayon";
import { ChildHome } from "@/components/learn/ChildHome";
import { api } from "@/lib/api";
import type { KcTutorCourse } from "@/lib/kc";
import type { Student, TutorProfile } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "My courses · AI Tutor" };

export default async function ChildHomePage({ params }: { params: Promise<{ studentId: string }> }) {
  const { studentId } = await params;
  let student: Student | null = null;
  let courses: KcTutorCourse[] = [];
  let tutors: TutorProfile[] = [];
  let error: string | null = null;
  try {
    const students = await api<Student[]>("/students");
    student = students.find((item) => item.id === studentId) ?? null;
    if (student) {
      [courses, tutors] = await Promise.all([
        api<KcTutorCourse[]>(`/kc/tutor/courses?student_id=${encodeURIComponent(studentId)}`),
        api<TutorProfile[]>("/tutor-profiles"),
      ]);
    }
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  if (!student) {
    return (
      <Crayon>
        <main className="cb-page">
          <h1 className="cb-course-title">That learner is not on this device.</h1>
          <p className="cb-muted-copy">{error || "Pick someone from the learner list."}</p>
          <Button tone="primary" href="/learn">
            Who&apos;s learning today?
          </Button>
        </main>
      </Crayon>
    );
  }
  return <ChildHome student={student} courses={courses} tutors={tutors} error={error} />;
}
