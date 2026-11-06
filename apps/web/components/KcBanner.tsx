import { BrandMark } from "@/components/BrandMark";

export function KcBanner({ name }: { name: string }) {
  return (
    <header className="kc-banner">
      <BrandMark />
      <h1>{name}</h1>
    </header>
  );
}
