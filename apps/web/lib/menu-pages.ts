export type MenuLink = { readonly href: string; readonly label: string };

export type MenuSection = {
  readonly id: string;
  readonly title: string;
  readonly links: readonly MenuLink[];
};

/** Student rows use UUID primary keys. Anything else is not a known child. */
const STUDENT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function knownStudentId(value: string | null | undefined): string | null {
  const id = (value ?? "").trim();
  return STUDENT_ID.test(id) ? id : null;
}

export const menuSections: readonly MenuSection[] = [
  {
    id: "kids",
    title: "Kids Portal",
    links: [{ href: "/learn", label: "Child chooser" }],
  },
  {
    id: "administration",
    title: "Administration",
    links: [
      { href: "/admin", label: "Admin" },
      { href: "/admin/kc-chats", label: "KC View Chats" },
      { href: "/viewkcchats", label: "View KC chats" },
      { href: "/admin/agent-customizations", label: "AI Tutor Configurations" },
      { href: "/documentation", label: "Documentation" },
    ],
  },
  {
    id: "creation",
    title: "KC course creation",
    links: [
      { href: "/kc-studio", label: "KC Course Creator" },
      { href: "/kc-creator", label: "KC Topic Creator" },
      { href: "/manage-kc-courses", label: "Manage KC courses" },
    ],
  },
  {
    id: "testing",
    title: "Testing pages",
    links: [
      { href: "/kc-tutor", label: "KC Tutor" },
      { href: "/kc-prompt-tester", label: "KC Prompt Tester" },
      { href: "/kc-progress", label: "Detailed Progress" },
    ],
  },
  {
    id: "deprecated",
    title: "Deprecated Pages",
    links: [
      { href: "/admin/lessons", label: "Lesson Desk" },
      { href: "/", label: "Home" },
      { href: "/create-course", label: "Create course" },
      { href: "/manage-courses", label: "Manage courses" },
      { href: "/viewchats", label: "View chats" },
    ],
  },
];

export function menuSectionsFor(studentId?: string | null): readonly MenuSection[] {
  const id = knownStudentId(studentId);
  if (!id) return menuSections;
  return menuSections.map((section) =>
    section.id === "kids"
      ? {
          ...section,
          links: [...section.links, { href: `/learn/${id}`, label: "Child home" }],
        }
      : section,
  );
}
