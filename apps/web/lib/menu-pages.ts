export const kcAndAdminPages = [
  { href: "/admin", label: "Admin" },
  { href: "/admin/agent-customizations", label: "Agent customizations" },
  { href: "/kc-studio", label: "KC Course Creator" },
  { href: "/manage-kc-courses", label: "Manage KC courses" },
  { href: "/kc-creator", label: "KC Creator" },
  { href: "/kc-tutor", label: "KC Tutor" },
  { href: "/kc-prompt-tester", label: "KC Prompt Tester" },
  { href: "/kc-progress", label: "KC Course Progress" },
  { href: "/viewkcchats", label: "View KC chats" },
  { href: "/documentation", label: "Documentation" },
] as const;

export const olderPages = [
  { href: "/", label: "Home" },
  { href: "/create-course", label: "Create course" },
  { href: "/manage-courses", label: "Manage courses" },
  { href: "/viewchats", label: "View chats" },
] as const;
