import type { Viewport } from "next";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
};

export default function LearnMobileLayout({ children }: { children: React.ReactNode }) {
  return children;
}
