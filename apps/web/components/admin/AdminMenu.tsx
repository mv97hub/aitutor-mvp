import Link from "next/link";

export const ADMIN_SECTIONS = [
  { id: "kc-chats", href: "/admin/kc-chats", label: "KC View Chats" },
  { id: "customizations", href: "/admin/agent-customizations", label: "AI Tutor Configurations" },
  { id: "ai-safety", href: "/admin/ai-safety", label: "AI Safety" },
  { id: "token-usage", href: "/admin/token-usage", label: "Token usage" },
] as const;

export const VISIBLE_ADMIN_SECTIONS = ADMIN_SECTIONS;

export type AdminSection = "kc-chats" | "customizations" | "ai-safety" | "token-usage" | "lessons" | "chats";

const CREATOR_LINKS = [
  { href: "/kc-studio", label: "KC Course Creator" },
  { href: "/kc-creator", label: "KC Topic Creator" },
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
        {CREATOR_LINKS.map((link) => (
          <Link key={link.href} href={link.href} className="ds-top-btn">
            {link.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
