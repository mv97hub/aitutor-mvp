import { KcPromptTester } from "@/components/KcPromptTester";
import { api } from "@/lib/api";
import type { KcCourse } from "@/lib/kc";
import type { Student, TutorProfile } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "KC Prompt Tester · AI Tutor" };

export default async function KcPromptTesterPage() {
  let courses: KcCourse[] = [];
  let students: Student[] = [];
  let profile: TutorProfile | null = null;
  let profiles: TutorProfile[] = [];
  let loadError: string | null = null;
  try {
    [courses, profile, students, profiles] = await Promise.all([
      api<KcCourse[]>("/kc/courses"),
      api<TutorProfile>("/tutor-profile"),
      api<Student[]>("/students"),
      api<TutorProfile[]>("/tutor-profiles").catch(() => []),
    ]);
  } catch (err) {
    loadError = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return (
    <KcPromptTester
      courses={courses}
      students={students}
      profile={profile}
      profiles={profiles}
      loadError={loadError}
    />
  );
}
