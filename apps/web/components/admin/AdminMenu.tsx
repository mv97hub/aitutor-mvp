import Link from "next/link";

export const ADMIN_SECTIONS = [
  { id: "lessons", href: "/admin", label: "Lesson Desk" },
  { id: "chats", href: "/viewchats", label: "View Chats" },
  { id: "kc-chats", href: "/viewkcchats", label: "View KC Chats" },
  { id: "customizations", href: "/admin/agent-customizations", label: "Agent Customizations" },
] as const;

export const VISIBLE_ADMIN_SECTIONS = ADMIN_SECTIONS.filter(
  (item) => item.id !== "lessons" && item.id !== "chats",
);

export type AdminSection = (typeof ADMIN_SECTIONS)[number]["id"];

export function AdminMenu({ current }: { current: AdminSection }) {
  return (
    <header className="ds-admin-bar">
      <p className="ds-admin-label">Administration</p>
      <nav className="ds-switch" aria-label="Administration">
        {VISIBLE_ADMIN_SECTIONS.map((item) => (
          <Link key={item.id} href={item.href} aria-current={item.id === current ? "page" : undefined}>
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
