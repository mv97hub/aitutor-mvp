import type { ReactNode } from "react";
import Link from "next/link";

import { BrandMark } from "@/components/BrandMark";
import { parentChats, parentHome, parentProgress, parentSettings } from "@/lib/parent";

export type ParentSection = "home" | "chats" | "progress" | "settings";

/** The parent area's own frame. It carries no admin bar and no debug controls. */
export function ParentFrame({
  parentId,
  parentName,
  studentId,
  current,
  sidebar,
  children,
}: {
  parentId: string;
  parentName: string;
  studentId?: string | null;
  current: ParentSection;
  sidebar?: ReactNode;
  children: ReactNode;
}) {
  const childId = studentId?.trim() || "";
  const links: { id: ParentSection; href: string | null; label: string }[] = [
    { id: "home", href: parentHome(parentId), label: "Dashboard" },
    { id: "chats", href: childId ? parentChats(parentId, childId) : null, label: "Chats" },
    { id: "progress", href: childId ? parentProgress(parentId, childId) : null, label: "Progress" },
    { id: "settings", href: parentSettings(parentId), label: "Settings" },
  ];
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
