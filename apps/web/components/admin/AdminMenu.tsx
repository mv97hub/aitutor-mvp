import Link from "next/link";

export const ADMIN_SECTIONS = [
  { id: "kc-chats", href: "/admin/kc-chats", label: "KC View Chats" },
  { id: "customizations", href: "/admin/agent-customizations", label: "AI Tutor Configurations" },
] as const;

export const VISIBLE_ADMIN_SECTIONS = ADMIN_SECTIONS;

export type AdminSection = "kc-chats" | "customizations" | "lessons" | "chats";

export const TOP_NAV_LINKS = [
  { href: "/kc-tutor", label: "KC Tutor" },
  { href: "/kc-progress", label: "KC Progress" },
  { href: "/kc-studio", label: "KC Course Creator" },
  { href: "/kc-creator", label: "KC Creator" },
  { href: "/admin", label: "Administration" },
] as const;

export function AdminMenu({ current }: { current: AdminSection }) {
  return (
    <header className="ds-admin-bar">
      <div className="ds-admin-brand">
        <p className="ds-admin-label">Administration</p>
      </div>
      <nav className="ds-switch" aria-label="Administration">
        {VISIBLE_ADMIN_SECTIONS.map((item) => {
          const isCurrent = item.id === current;
          return (
            <Link
              key={item.id}
              href={item.href}
              className={`ds-top-btn${isCurrent ? " is-active" : ""}`}
              aria-current={isCurrent ? "page" : undefined}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <nav className="ds-admin-shortcuts" aria-label="Workspace navigation">
        {TOP_NAV_LINKS.filter((link) => link.href !== "/admin").map((link) => (
          <Link key={link.href} href={link.href} className="ds-top-btn is-shortcut">
            {link.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
