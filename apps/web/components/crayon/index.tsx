"use client";

import { Lexend } from "next/font/google";
import Link from "next/link";
import {
  useEffect,
  useId,
  useState,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";

const lexend = Lexend({
  subsets: ["latin"],
  weight: ["400", "600", "800"],
  display: "swap",
  fallback: ["system-ui", "sans-serif"],
  adjustFontFallback: false,
});

export type CrayonTone = "surface" | "yellow" | "blue" | "pink" | "sky" | "green";
export type CrayonShadow = "sm" | "md" | "lg" | "none";

export type CrayonNavItem = {
  href: string;
  label: string;
  active?: boolean;
};

export type StackSegment = {
  id: string;
  label: string;
  count: number;
  tone: "green" | "blue" | "yellow" | "track";
};

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

function clampPercent(value: number, max: number): number {
  if (!Number.isFinite(value) || !Number.isFinite(max) || max <= 0) return 0;
  return Math.min(100, Math.max(0, (value / max) * 100));
}

function countOf(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 0;
  return value;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase();
}

export function Crayon({
  children,
  className,
  ...rest
}: { children: ReactNode } & HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx("crayon", lexend.className, className)} {...rest}>
      {children}
    </div>
  );
}

export function Block({
  as: Tag = "div",
  tone = "surface",
  shadow = "md",
  className,
  children,
  ...rest
}: {
  as?: "div" | "section" | "article";
  tone?: CrayonTone;
  shadow?: CrayonShadow;
  children: ReactNode;
} & HTMLAttributes<HTMLElement>) {
  return (
    <Tag
      className={cx(
        "cb-block",
        `is-${tone}`,
        shadow === "none" ? "is-flat" : shadow === "md" ? null : `is-shadow-${shadow}`,
        className,
      )}
      {...rest}
    >
      {children}
    </Tag>
  );
}

export function Card({
  band,
  shadow = "md",
  className,
  children,
  ...rest
}: {
  band?: CrayonTone;
  shadow?: CrayonShadow;
  children: ReactNode;
} & HTMLAttributes<HTMLElement>) {
  return (
    <article
      className={cx("cb-card", shadow === "none" ? "is-flat" : shadow === "md" ? null : `is-shadow-${shadow}`, className)}
      {...rest}
    >
      {band ? <div className={cx("cb-card-band", `is-${band}`)} aria-hidden="true" /> : null}
      <div className="cb-card-body">{children}</div>
    </article>
  );
}

type ButtonLook = {
  children: ReactNode;
  tone?: "primary" | "secondary";
  square?: boolean;
  className?: string;
};

type ButtonProps = ButtonLook &
  (
    | ({ href: string } & Omit<HTMLAttributes<HTMLAnchorElement>, "className" | "children">)
    | ({ href?: undefined } & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "children">)
  );

export function Button({ children, tone = "secondary", square = false, className, ...props }: ButtonProps) {
  const classes = cx("cb-btn", tone === "primary" ? "is-primary" : "is-secondary", square && "is-square", className);
  if ("href" in props && props.href) {
    const { href, ...rest } = props;
    return (
      <Link href={href} className={classes} {...rest}>
        {children}
      </Link>
    );
  }
  const buttonProps = props as Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "children">;
  const { type = "button", ...rest } = buttonProps;
  return (
    <button type={type} className={classes} {...rest}>
      {children}
    </button>
  );
}

export function Tag({
  children,
  tone = "surface",
  className,
}: {
  children: ReactNode;
  tone?: CrayonTone;
  className?: string;
}) {
  return <span className={cx("cb-tag", `is-${tone}`, className)}>{children}</span>;
}

export function FilterChip({
  children,
  pressed = false,
  tone = "yellow",
  wide = false,
  className,
  ...props
}: {
  children: ReactNode;
  pressed?: boolean;
  tone?: "yellow" | "blue";
  wide?: boolean;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children">) {
  return (
    <button
      {...props}
      type="button"
      aria-pressed={pressed}
      className={cx("cb-chip", tone === "blue" && "is-blue", wide && "is-wide", className)}
    >
      {children}
    </button>
  );
}

export function SegmentedControl({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="cb-segment" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function ProgressBar({
  value,
  max = 100,
  caption,
  tone = "blue",
}: {
  value: number;
  max?: number;
  caption?: string;
  tone?: "blue" | "green";
}) {
  const pct = clampPercent(value, max);
  return (
    <div className="cb-progress">
      <div
        className="cb-progress-track"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={caption ?? `${Math.round(pct)} percent`}
      >
        <div className={cx("cb-progress-fill", tone === "green" && "is-green")} style={{ width: `${pct}%` }} />
      </div>
      {caption ? <p className="cb-progress-caption">{caption}</p> : null}
    </div>
  );
}

export function StackedBar({ segments }: { segments: readonly StackSegment[] }) {
  const counts = segments.map((segment) => countOf(segment.count));
  const total = counts.reduce((sum, count) => sum + count, 0);
  const summary = segments.map((segment, index) => `${segment.label} ${counts[index]}`).join(", ");
  return (
    <div className="cb-stack">
      <div className="cb-stack-track" role="img" aria-label={summary}>
        {segments.map((segment, index) => (
          <div
            key={segment.id}
            className={cx("cb-stack-seg", `is-${segment.tone}`)}
            style={{ width: total === 0 ? "0%" : `${(counts[index] / total) * 100}%` }}
          />
        ))}
      </div>
      <ul className="cb-legend">
        {segments.map((segment, index) => (
          <li key={segment.id}>
            <span className={cx("cb-swatch", `is-${segment.tone}`)} aria-hidden="true" />
            <span>{segment.label}</span>
            <span>{counts[index]}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ProgressRing({
  value,
  label,
  size = 96,
}: {
  value: number;
  label: string;
  size?: number;
}) {
  const pct = clampPercent(value, 100);
  return (
    <div className="cb-ring" style={{ width: size, height: size }} role="img" aria-label={label}>
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle className="cb-ring-track" cx="50" cy="50" r="36" />
        <circle
          className="cb-ring-value"
          cx="50"
          cy="50"
          r="36"
          pathLength={100}
          strokeDasharray={`${pct} ${100 - pct}`}
        />
      </svg>
      <span className="cb-ring-pct" aria-hidden="true">
        {Math.round(pct)}%
      </span>
    </div>
  );
}

export function Avatar({
  name,
  tone = "pink",
  size = 40,
  className,
}: {
  name: string;
  tone?: CrayonTone;
  size?: number;
  className?: string;
}) {
  const letters = initials(name);
  const fontSize = Math.max(15, Math.round(size * 0.34));
  return (
    <span
      className={cx("cb-avatar", `is-${tone}`, className)}
      style={{ width: size, height: size, fontSize }}
      role="img"
      aria-label={name}
    >
      {letters}
    </span>
  );
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="cb-section">
      <h2 className="cb-section-title">{children}</h2>
      {action}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="cb-empty">
      <p className="cb-empty-title">{title}</p>
      {children ? <div className="cb-empty-action">{children}</div> : null}
    </div>
  );
}

export function Input({
  label,
  hideLabel = false,
  id,
  className,
  ...props
}: { label: string; hideLabel?: boolean } & InputHTMLAttributes<HTMLInputElement>) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  return (
    <label className="cb-field" htmlFor={inputId}>
      <span className={cx("cb-field-label", hideLabel && "is-hidden")}>{label}</span>
      <input id={inputId} className={cx("cb-input", className)} {...props} />
    </label>
  );
}

export function TopBar({
  appName,
  items,
  studentName,
}: {
  appName: string;
  items: readonly CrayonNavItem[];
  studentName?: string;
}) {
  const [open, setOpen] = useState(false);
  const navId = useId();

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header className={cx("cb-topbar", open && "is-open")}>
      <div className="cb-brand">
        <img className="cb-logo" src="/kinder-computers-logo.png" alt="" width={32} height={32} />
        <span className="cb-app-name">{appName}</span>
      </div>
      {items.length > 0 ? (
        <button
          type="button"
          className="cb-btn cb-menu"
          aria-expanded={open}
          aria-controls={navId}
          onClick={() => setOpen((current) => !current)}
        >
          Menu
        </button>
      ) : null}
      {items.length > 0 ? (
        <nav id={navId} className="cb-nav" aria-label="Primary">
          {items.map((item, index) => (
            <Link
              key={`${item.label}:${item.href}:${index}`}
              href={item.href}
              className={cx("cb-pill", item.active && "is-active")}
              aria-current={item.active ? "page" : undefined}
              onClick={() => setOpen(false)}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      ) : null}
      {studentName ? <Avatar name={studentName} tone="pink" /> : null}
    </header>
  );
}
