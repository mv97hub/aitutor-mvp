import Link from "next/link";

export function DeskSwitch({ current }: { current: "admin" | "chats" }) {
  return (
    <nav className="ds-switch" aria-label="Switch page">
      <Link href="/admin" aria-current={current === "admin" ? "page" : undefined}>
        Lesson desk
      </Link>
      <Link href="/viewchats" aria-current={current === "chats" ? "page" : undefined}>
        View chats
      </Link>
    </nav>
  );
}
