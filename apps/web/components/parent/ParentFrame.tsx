"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { BrandMark } from "@/components/BrandMark";
import { parentChildHref, parentChats, parentHome, parentProgress, parentSettings, type ParentSection } from "@/lib/parent";

export type { ParentSection };

export type ParentLearner = { id: string; display_name: string };

/** The parent area's own frame. It carries no admin bar and no debug controls. */
export function ParentFrame({
  parentId,
  parentName,
  studentId,
  learners = [],
  onStudentChange,
  current,
  sidebar,
  children,
}: {
  parentId: string;
  parentName: string;
  studentId?: string | null;
  learners?: ParentLearner[];
  onStudentChange?: (studentId: string) => void;
  current: ParentSection;
  sidebar?: ReactNode;
  children: ReactNode;
}) {
  const router = useRouter();
  const childId = studentId?.trim() || "";
  const links: { id: ParentSection; href: string | null; label: string }[] = [
    { id: "home", href: parentHome(parentId), label: "Dashboard" },
    { id: "chats", href: childId ? parentChats(parentId, childId) : null, label: "Chats" },
    { id: "progress", href: childId ? parentProgress(parentId, childId) : null, label: "Progress" },
    { id: "settings", href: parentSettings(parentId), label: "Settings" },
  ];

  function chooseChild(nextId: string) {
    if (!nextId || nextId === childId) return;
    const href = parentChildHref(current, parentId, nextId);
    if (href) {
      router.push(href);
      return;
    }
    onStudentChange?.(nextId);
  }

  return (
    <main className={`ds-shell ds-desk ds-admin parent-frame${sidebar ? " has-sidebar" : " no-sidebar"}`}>
      <header className="ds-admin-bar">
        <div className="ds-admin-brand">
          <p className="ds-admin-label">Parent portal · {parentName}</p>
        </div>
        <nav className="ds-switch" aria-label="Parent portal">
          {links.map((item) => {
            const active = item.id === current;
            const className = `ds-top-btn${active ? " is-active" : ""}`;
            if (!item.href) {
              return (
                <span key={item.id} className={`${className} is-disabled`} aria-disabled="true" title="Choose a child first">
                  {item.label}
                </span>
              );
            }
            return (
              <Link key={item.id} href={item.href} className={className} aria-current={active ? "page" : undefined}>
                {item.label}
              </Link>
            );
          })}
        </nav>
        {learners.length > 0 ? (
          <label className="parent-child-menu">
            <span aria-hidden="true">Child</span>
            <select aria-label="Child" value={childId} onChange={(event) => chooseChild(event.target.value)}>
              {childId ? null : <option value="">Choose a child</option>}
              {learners.map((learner) => (
                <option key={learner.id} value={learner.id}>
                  {learner.display_name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </header>
      {sidebar ? (
        <aside className="ds-side">
          <div className="ds-logo">
            <BrandMark />
          </div>
          {sidebar}
        </aside>
      ) : null}
      <section className="ds-work">{children}</section>
    </main>
  );
}
