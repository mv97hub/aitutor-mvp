import Link from "next/link";

import { BrandMark } from "@/components/BrandMark";
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
      <main className="learn-shell">
        <BrandMark />
        <h1>That learner is not on this device.</h1>
        <p className="lede">{error || "Pick someone from the learner list."}</p>
        <Link href="/learn" className="learn-btn primary">
          Who&apos;s learning today?
        </Link>
      </main>
    );
  }
  return <ChildHome student={student} courses={courses} tutors={tutors} error={error} />;
}
