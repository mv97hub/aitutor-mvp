import type { ReactNode } from "react";

import { BrandMark } from "@/components/BrandMark";

export function KcBanner({ name, children }: { name: string; children?: ReactNode }) {
  return (
    <header className="kc-banner">
      <BrandMark />
      <h1>{name}</h1>
      {children}
    </header>
  );
}
