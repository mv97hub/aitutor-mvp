import Link from "next/link";

import { BrandMark } from "@/components/BrandMark";

export function ParentMissing({ title, detail }: { title: string; detail: string }) {
  return (
    <main className="learn-shell parent-shell">
      <BrandMark />
      <h1>{title}</h1>
      <p className="lede">{detail}</p>
      <Link href="/parent" className="learn-btn primary">
        Back to the parent list
      </Link>
    </main>
  );
}
