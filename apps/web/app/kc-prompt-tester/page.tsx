import { KcPromptTester } from "@/components/KcPromptTester";
import { api } from "@/lib/api";
import type { KcCourse } from "@/lib/kc";
import type { TutorProfile } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "KC Prompt Tester · AI Tutor" };

export default async function KcPromptTesterPage() {
  let courses: KcCourse[] = [];
  let profile: TutorProfile | null = null;
  let loadError: string | null = null;
  try {
    [courses, profile] = await Promise.all([api<KcCourse[]>("/kc/courses"), api<TutorProfile>("/tutor-profile")]);
  } catch (err) {
    loadError = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return <KcPromptTester courses={courses} profile={profile} loadError={loadError} />;
}
