import { redirect } from "next/navigation";

import { LearnMobileTutor } from "@/components/learn/LearnMobileTutor";
import { api } from "@/lib/api";
import type { KcChatSummary, KcProgress, KcTutorCourse, KcTutorSession } from "@/lib/kc";
import { kcModel } from "@/lib/kc-models";
import { learnMobileCoursePath, tutorForSession } from "@/lib/learn-mobile";
import type { Student, TutorProfile } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Course tutor · AI Tutor" };

export default async function MobileCourseTutorPage({
  params,
  searchParams,
}: {
  params: Promise<{ studentId: string; courseId: string }>;
  searchParams: Promise<{ session?: string; kc?: string; model?: string; error?: string }>;
}) {
  const { studentId, courseId } = await params;
  const query = await searchParams;
  let students: Student[] = [];
  let courses: KcTutorCourse[] = [];
  let tutorProfiles: TutorProfile[] = [];
  let progress: KcProgress | null = null;
  let session: KcTutorSession | null = null;
  let error: string | null = query.error ? decodeURIComponent(query.error) : null;
  let redirectTo: string | null = null;
  try {
    [students, courses, tutorProfiles] = await Promise.all([
      api<Student[]>("/students"),
      api<KcTutorCourse[]>(`/kc/tutor/courses?student_id=${encodeURIComponent(studentId)}`),
      api<TutorProfile[]>("/tutor-profiles").catch(() => []),
    ]);
    progress = await api<KcProgress>(`/kc/tutor/courses/${courseId}?student_id=${encodeURIComponent(studentId)}`);
    const course = courses.find((item) => item.id === courseId) ?? null;
    const tutorId = course?.tutor?.id;
    if (query.session && !query.kc) {
      session = await api<KcTutorSession>(`/kc/tutor/sessions/${query.session}`);
      if (session.course_id !== courseId) {
        session = null;
        error = "That session belongs to another course.";
      }
    } else if (query.kc) {
      const chats = await api<KcChatSummary[]>(`/kc/sessions?student_id=${encodeURIComponent(studentId)}`);
      const matches = chats
        .filter((chat) => chat.kc_id === query.kc && chat.course_id === courseId)
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
      const existing = matches.find((chat) => chat.status === "in_progress") ?? matches[0];
      if (existing && existing.status === "completed") {
        session = await api<KcTutorSession>(`/kc/tutor/sessions/${existing.id}`);
      } else {
        session = await api<KcTutorSession>("/kc/tutor/sessions", {
          method: "POST",
          body: JSON.stringify({
            student_id: studentId,
            course_id: courseId,
            kc_id: query.kc,
            tutor_profile_id: tutorId,
          }),
        });
      }
      redirectTo = learnMobileCoursePath(studentId, courseId, { session: session.id });
    } else {
      session = await api<KcTutorSession>("/kc/tutor/start", {
        method: "POST",
        body: JSON.stringify({ student_id: studentId, course_id: courseId }),
      });
      redirectTo = learnMobileCoursePath(studentId, courseId, { session: session.id });
    }
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
    redirectTo = null;
  }
  if (redirectTo) redirect(redirectTo);
  const learner = students.find((item) => item.id === studentId) ?? null;
  const course = courses.find((item) => item.id === courseId) ?? null;
  return (
    <LearnMobileTutor
      studentId={studentId}
      courseId={courseId}
      courseTitle={course?.title || progress?.title || "Course"}
      stars={course?.stars ?? progress?.stars ?? 0}
      progress={progress}
      session={session}
      error={error}
      tutor={tutorForSession(tutorProfiles, session, learner?.preferred_tutor_profile_id)}
      model={kcModel(query.model)}
    />
  );
}
