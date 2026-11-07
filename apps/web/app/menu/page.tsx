import Link from "next/link";

export const metadata = { title: "Menu · AI Tutor" };

const pages = [
  { href: "/", label: "Home" },
  { href: "/admin", label: "Admin" },
  { href: "/admin/agent-customizations", label: "Agent customizations" },
  { href: "/create-course", label: "Create course" },
  { href: "/manage-courses", label: "Manage courses" },
  { href: "/viewchats", label: "View chats" },
  { href: "/viewkcchats", label: "View KC chats" },
  { href: "/kc-studio", label: "KC Course Creator" },
  { href: "/manage-kc-courses", label: "Manage KC courses" },
  { href: "/kc-creator", label: "KC Creator" },
  { href: "/kc-tutor", label: "KC Tutor" },
  { href: "/documentation", label: "Documentation" },
] as const;

export default function MenuPage() {
  return (
    <main className="ds-landing">
      <section className="ds-landing-card">
        <h1>Menu</h1>
        <nav aria-label="Pages">
          <ul>
            {pages.map((page) => (
              <li key={page.href}>
                <Link href={page.href}>{page.label}</Link>
              </li>
            ))}
          </ul>
        </nav>
      </section>
    </main>
  );
}
