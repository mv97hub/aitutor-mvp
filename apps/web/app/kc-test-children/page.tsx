import { HarnessApp } from "@/components/harness/HarnessApp";
import type { HarnessPersona } from "@/components/harness/ProfilesView";
import { api } from "@/lib/api";
import type { KcCourse } from "@/lib/kc";
import type { TutorProfile } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "AI Test Children · AI Tutor" };

export default async function KcTestChildrenPage() {
  let personas: HarnessPersona[] = [];
  let courses: KcCourse[] = [];
  let profiles: TutorProfile[] = [];
  let loadError: string | null = null;
  try {
    [personas, courses, profiles] = await Promise.all([
      api<HarnessPersona[]>("/kc/harness/personas?include_archived=true"),
      api<KcCourse[]>("/kc/courses"),
      api<TutorProfile[]>("/tutor-profiles").catch(() => []),
    ]);
  } catch (err) {
    loadError = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return <HarnessApp personas={personas} courses={courses} profiles={profiles} loadError={loadError} />;
}
