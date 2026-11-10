import Link from "next/link";

import { TutorAvatar } from "@/components/TutorAvatar";
import { api } from "@/lib/api";
import type { KcTutorCourse } from "@/lib/kc";
import type { Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Course tutor · AI Tutor" };

export default async function CourseTutorPage({
  params,
}: {
  params: Promise<{ studentId: string; courseId: string }>;
}) {
  const { studentId, courseId } = await params;
  let student: Student | null = null;
  let course: KcTutorCourse | null = null;
  let error: string | null = null;
  try {
    const [students, courses] = await Promise.all([
      api<Student[]>("/students"),
      api<KcTutorCourse[]>(`/kc/tutor/courses?student_id=${encodeURIComponent(studentId)}`),
    ]);
    student = students.find((item) => item.id === studentId) ?? null;
    course = courses.find((item) => item.id === courseId) ?? null;
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return (
    <main className="learn-shell">
      <Link href={`/learn/${studentId}`} className="learn-switch">
        ← Back to My Courses
      </Link>
      <h1>{course?.title || "Course"}</h1>
      {error ? (
        <div className="banner" role="alert">
          <p>{error}</p>
        </div>
      ) : null}
      {course?.tutor ? (
        <p className="learn-guided">
          <TutorAvatar
            preset={course.tutor.avatar_preset}
            avatarUrl={course.tutor.avatar_url}
            name={course.tutor.name}
            size="lg"
          />
          {course.tutor.name} is ready for {student?.display_name || "you"}.
        </p>
      ) : (
        <p className="lede">This course is opening.</p>
      )}
      <p className="learn-meta">
        {course?.completed_count ?? 0} of {course?.component_count ?? 0} topics · ★ {course?.stars ?? 0}
      </p>
    </main>
  );
}
