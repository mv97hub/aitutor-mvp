export type TutorQuery = {
  student?: string;
  course?: string;
  kc?: string;
  session?: string;
  model?: string;
};

export function tutorPath(parts: TutorQuery) {
  const params = new URLSearchParams();
  if (parts.student) params.set("student", parts.student);
  if (parts.course) params.set("course", parts.course);
  if (parts.kc) params.set("kc", parts.kc);
  if (parts.session) params.set("session", parts.session);
  if (parts.model) params.set("model", parts.model);
  const query = params.toString();
  return query ? `/kc-tutor?${query}` : "/kc-tutor";
}

export type TutorSessionTarget =
  | { kind: "load"; sessionId: string }
  | { kind: "open"; studentId: string; courseId: string; kcId: string }
  | { kind: "none" };

/** A session id in the URL is loaded. A component without one is opened once. */
export function tutorSessionTarget(params: TutorQuery): TutorSessionTarget {
  if (params.session) return { kind: "load", sessionId: params.session };
  if (params.student && params.course && params.kc) {
    return { kind: "open", studentId: params.student, courseId: params.course, kcId: params.kc };
  }
  return { kind: "none" };
}

/** After the first open, the URL names that session and does not ask to open again. */
export function openedSessionPath(params: TutorQuery, sessionId: string) {
  return tutorPath({
    student: params.student,
    course: params.course,
    session: sessionId,
    model: params.model,
  });
}
