import type { ReactNode } from "react";

/** A heading and its list, the same block Detailed Progress uses for revisit notes. */
export function ProgressRecommend({
  heading,
  level = "h2",
  label,
  children,
}: {
  heading: string;
  level?: "h2" | "h3";
  label?: string;
  children: ReactNode;
}) {
  const Title = level;
  return (
    <section className="progress-recommend" aria-label={label ?? heading}>
      <Title>{heading}</Title>
      {children}
    </section>
  );
}
