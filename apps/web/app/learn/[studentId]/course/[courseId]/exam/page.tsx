import { BlindExamClient } from "@/components/learn/BlindExamClient";
import { api } from "@/lib/api";
import { normalizeExamPhase, type CourseExamSummary } from "@/lib/blind-exam";
import type { Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Course check · AI Tutor" };

export default async function BlindExamPage({
  params,
  searchParams,
}: {
  params: Promise<{ studentId: string; courseId: string }>;
  searchParams: Promise<{ phase?: string }>;
}) {
  const { studentId, courseId } = await params;
  const query = await searchParams;
  const phase = normalizeExamPhase(query.phase);

  const [students, summary] = await Promise.all([
    api<Student[]>("/students").catch(() => []),
    api<CourseExamSummary>(
      `/kc/tutor/courses/${encodeURIComponent(courseId)}/exam?student_id=${encodeURIComponent(studentId)}&phase=${phase}`,
    ).catch(() => null),
  ]);

  const student = students.find((row) => row.id === studentId) ?? null;

  return (
    <BlindExamClient
      studentId={studentId}
      studentName={student?.display_name ?? ""}
      courseId={courseId}
      courseTitle={summary?.course_title ?? "Course"}
      tutorModel={student?.tutor_model ?? null}
      phase={phase}
      initialExam={summary?.exam ?? null}
      initialPreScore={summary?.pre_score ?? null}
      initialLatestAttempt={phase === "pre" ? (summary?.pre_attempt ?? null) : (summary?.post_attempt ?? null)}
    />
  );
}
