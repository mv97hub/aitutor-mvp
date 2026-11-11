import type { ReactNode } from "react";
import Link from "next/link";

import { BrandMark } from "@/components/BrandMark";
import { parentChats, parentHome, parentProgress, parentSettings } from "@/lib/parent";

export type ParentSection = "chats" | "progress";

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
  studentId: string;
  current: ParentSection;
  sidebar?: ReactNode;
  children: ReactNode;
}) {
  const links: { id: ParentSection | "home" | "settings"; href: string; label: string }[] = [
    { id: "home", href: parentHome(parentId), label: "Dashboard" },
    { id: "chats", href: parentChats(parentId, studentId), label: "Chats" },
    { id: "progress", href: parentProgress(parentId, studentId), label: "Progress" },
    { id: "settings", href: parentSettings(parentId), label: "Settings" },
  ];
  return (
    <main className="ds-shell ds-desk ds-admin parent-frame">
      <header className="ds-admin-bar">
        <div className="ds-admin-brand">
          <p className="ds-admin-label">Parent portal · {parentName}</p>
        </div>
        <nav className="ds-switch" aria-label="Parent portal">
          {links.map((item) => (
            <Link key={item.id} href={item.href} aria-current={item.id === current ? "page" : undefined}>
              {item.label}
            </Link>
          ))}
        </nav>
      </header>
      <aside className="ds-side">
        <div className="ds-logo">
          <BrandMark />
        </div>
        {sidebar}
      </aside>
      <section className="ds-work">{children}</section>
    </main>
  );
}
