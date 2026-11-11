import { knownStudentId } from "./menu-pages.ts";

/** There is no login. A parent id in the URL is the only gate, like the kid pages. */
export type Parent = {
  id: string;
  name: string;
  created_at: string;
  child_count: number;
};

export type ParentChatSummary = {
  id: string;
  student_id: string;
  student_display_name: string;
  course_id: string;
  course_code: string;
  course_title: string;
  kc_id: string;
  kc_code: string;
  kc_title: string;
  step_label: string;
  status: string;
  score: number | null;
  created_at: string;
  updated_at: string;
  message_count: number;
};

/** The parent chat detail has no prompts key. The server never sends one. */
export type ParentChatDetail = {
  id: string;
  status: string;
  step_label: string;
  score: number | null;
  attempts: number;
  created_at: string;
  updated_at: string;
  student: { id: string; display_name: string };
  course: { id: string; code: string; title: string };
  component: { id: string; code: string; title: string };
  messages: { id: string; role: "user" | "assistant"; content: string; seq: number; created_at: string }[];
};

/** Ids are UUIDs. Anything else is not a parent, child, or chat. */
export function knownId(value: string | null | undefined): string | null {
  return knownStudentId(value);
}

export function parentHome(parentId: string): string {
  return `/parent/${parentId}`;
}

export function parentSettings(parentId: string): string {
  return `/parent/${parentId}/settings`;
}

export function parentChats(parentId: string, studentId: string): string {
  return `/parent/${parentId}/child/${studentId}/chats`;
}

export function parentProgress(parentId: string, studentId: string, courseId?: string): string {
  const base = `/parent/${parentId}/child/${studentId}/progress`;
  return courseId ? `${base}?course=${encodeURIComponent(courseId)}` : base;
}

export function childCountLabel(count: number): string {
  if (count <= 0) return "No children linked yet";
  return count === 1 ? "1 child" : `${count} children`;
}

/** The ids to save when a child is ticked or unticked in settings. */
export function toggledIds(current: readonly string[], id: string, on: boolean): string[] {
  const rest = current.filter((item) => item !== id);
  return on ? [...rest, id] : rest;
}

/** A new parent, or one with no children, goes to settings first. */
export function landingPathFor(parent: Pick<Parent, "id" | "child_count">): string {
  return parent.child_count > 0 ? parentHome(parent.id) : parentSettings(parent.id);
}
