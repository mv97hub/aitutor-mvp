import { AdminApp } from "@/components/AdminApp";
import { api } from "@/lib/api";
import type { CourseSummary, CourseTree } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Lesson desk · AI Tutor" };

export default async function AdminPage() {
  let courses: CourseSummary[] = [];
  let tree: CourseTree | null = null;
  let error: string | null = null;
  try {
    courses = await api<CourseSummary[]>("/courses");
    const selected = courses[0];
    if (selected) tree = await api<CourseTree>(`/courses/${selected.id}`);
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return <AdminApp initialCourses={courses} initialTree={tree} initialError={error} />;
}
