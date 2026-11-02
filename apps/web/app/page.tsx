import { KidSession } from "@/components/KidSession";
import { api } from "@/lib/api";
import type { LessonPlanSummary, Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Lesson · AI Tutor" };

export default async function Page() {
  let students: Student[] = [];
  let plans: LessonPlanSummary[] = [];
  let error: string | null = null;
  try {
    [students, plans] = await Promise.all([
      api<Student[]>("/students"),
      api<LessonPlanSummary[]>("/lesson-plans"),
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return <KidSession initialStudents={students} initialPlans={plans} initialError={error} />;
}
