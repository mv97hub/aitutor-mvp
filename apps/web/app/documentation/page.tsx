import Link from "next/link";

export const metadata = { title: "Documentation · AI Tutor" };

const sections = [
  { href: "/documentation/kid-tutor", label: "Kid tutor" },
  { href: "/documentation/admin", label: "Admin" },
  { href: "/documentation/ai-safety", label: "AI Safety" },
  { href: "/documentation/parent-portal", label: "Parent portal" },
  { href: "/documentation/create-course", label: "Create course" },
  { href: "/documentation/view-chats", label: "View chats" },
  { href: "/documentation/view-kc-chats", label: "View KC chats" },
  { href: "/documentation/kc-studio", label: "KC Course Creator" },
  { href: "/documentation/manage-kc-courses", label: "Manage KC courses" },
  { href: "/documentation/kc-creator", label: "KC Creator" },
  { href: "/documentation/kc-tutor", label: "KC Tutor" },
  { href: "/documentation/kc-prompt-layers", label: "KC prompt layers" },
  { href: "/documentation/ai-test-children", label: "AI Test Children" },
] as const;

export default function DocumentationPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card">
        <h1>Documentation</h1>
        <nav aria-label="Sections">
          <ul>
            {sections.map((section) => (
              <li key={section.href}>
                <Link href={section.href}>{section.label}</Link>
              </li>
            ))}
          </ul>
        </nav>
      </article>
    </main>
  );
}
