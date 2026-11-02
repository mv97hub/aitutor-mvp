import Link from "next/link";

export const ADMIN_SECTIONS = [
  { id: "lessons", href: "/admin", label: "Lesson Desk", menu: true },
  { id: "chats", href: "/viewchats", label: "View Chats", menu: true },
  // Routes stay at these hrefs. Hidden until the pages are filled in.
  { id: "agents", href: "/admin/agent-profiles", label: "Agent Profiles", menu: false },
  { id: "tutor", href: "/admin/tutor-configuration", label: "Tutor Configuration", menu: false },
] as const;

export type AdminSection = (typeof ADMIN_SECTIONS)[number]["id"];

export function AdminMenu({ current }: { current: AdminSection }) {
  return (
    <header className="ds-admin-bar">
      <p className="ds-admin-label">Administration</p>
      <nav className="ds-switch" aria-label="Administration">
        {ADMIN_SECTIONS.filter((item) => item.menu).map((item) => (
          <Link key={item.id} href={item.href} aria-current={item.id === current ? "page" : undefined}>
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
