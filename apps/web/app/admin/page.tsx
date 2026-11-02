import { AdminApp } from "@/components/AdminApp";
import { api } from "@/lib/api";
import type { LessonPlan, LessonPlanSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Lesson desk · AI Tutor" };

export default async function AdminPage() {
  let plans: LessonPlanSummary[] = [];
  let plan: LessonPlan | null = null;
  let error: string | null = null;
  try {
    plans = await api<LessonPlanSummary[]>("/lesson-plans");
    const selected = plans.find((item) => item.is_active) ?? plans[0];
    if (selected) plan = await api<LessonPlan>(`/lesson-plans/${selected.id}`);
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return (
    <AdminApp
      initialPlans={plans}
      initialPlan={plan}
      initialError={error}
    />
  );
}
