import { AdminApp } from "@/components/AdminApp";
import { api } from "@/lib/api";
import type { LessonPlan, LessonPlanSummary, Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Lesson desk · AI Tutor" };

export default async function AdminPage() {
  let plans: LessonPlanSummary[] = [];
  let students: Student[] = [];
  let plan: LessonPlan | null = null;
  let error: string | null = null;
  try {
    [plans, students] = await Promise.all([
      api<LessonPlanSummary[]>("/lesson-plans"),
      api<Student[]>("/students"),
    ]);
    const selected = plans.find((item) => item.is_active) ?? plans[0];
    if (selected) plan = await api<LessonPlan>(`/lesson-plans/${selected.id}`);
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return (
    <AdminApp
      initialPlans={plans}
      initialStudents={students}
      initialPlan={plan}
      initialError={error}
    />
  );
}
