import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const crayonCss = readFileSync(join(root, "app/crayon.css"), "utf8");
const globalsCss = readFileSync(join(root, "app/globals.css"), "utf8");
const crayonTsx = readFileSync(join(root, "components/crayon/index.tsx"), "utf8");

const tokens: Record<string, string> = {
  "--cb-bg": "#fffdf7",
  "--cb-surface": "#ffffff",
  "--cb-ink": "#111111",
  "--cb-muted": "#4a4a4a",
  "--cb-line": "#111111",
  "--cb-track": "#efefef",
  "--cb-blue": "#3b5bfd",
  "--cb-yellow": "#ffd43b",
  "--cb-pink": "#ff7ab6",
  "--cb-green": "#22c55e",
  "--cb-sky": "#7dd3fc",
  "--cb-tutor-bubble": "#ffe8f3",
  "--cb-r": "14px",
  "--cb-r-sm": "10px",
  "--cb-bw": "2px",
  "--cb-shadow": "4px 4px 0 var(--cb-line)",
  "--cb-shadow-sm": "2px 2px 0 var(--cb-line)",
  "--cb-shadow-lg": "6px 6px 0 var(--cb-line)",
};

test("crayon tokens live on .crayon and keep the names from the rule", () => {
  assert.match(crayonCss, /\.crayon\s*\{[^}]*font-family:\s*Lexend,\s*system-ui,\s*sans-serif;/s);
  assert.match(crayonCss, /\.crayon\s*\{[^}]*background:\s*var\(--cb-bg\);/s);
  for (const [name, value] of Object.entries(tokens)) {
    assert.match(crayonCss, new RegExp(`${name.replace("-", "\\-")}:\\s*${value.replace(/[()]/g, "\\$&")}`));
  }
  assert.equal(globalsCss.includes("--cb-"), false);
  assert.match(globalsCss, /--ink:\s*#1c1915;/);
  assert.match(globalsCss, /--line:\s*#e2d3bd;/);
  assert.match(globalsCss, /--shadow:\s*0 18px 40px rgba\(48, 32, 12, 0\.08\);/);
  assert.match(globalsCss, /body\s*\{[^}]*radial-gradient\(circle at 8% 0%/s);
  assert.equal(crayonCss.includes("@tailwind"), false);
  assert.equal(crayonTsx.includes("tailwind"), false);
});

test("crayon selectors stay under the wrapper", () => {
  const withoutComments = crayonCss.replace(/\/\*[\s\S]*?\*\//g, "");
  const blocks = [...withoutComments.matchAll(/([^{}@]+)\{/g)].map((match) => match[1]);
  for (const block of blocks) {
    for (const selector of block.split(",")) {
      const trimmed = selector.trim();
      if (!trimmed || trimmed.startsWith("(") || trimmed.includes("media")) continue;
      assert.equal(trimmed.startsWith(".crayon"), true, trimmed);
    }
  }
});

test("components use token classes and no hardcoded hex", () => {
  assert.equal(/#[0-9a-fA-F]{3,8}\b/.test(crayonTsx), false);
  for (const name of [
    "Crayon",
    "Block",
    "Card",
    "Button",
    "Tag",
    "FilterChip",
    "SegmentedControl",
    "ProgressBar",
    "StackedBar",
    "ProgressRing",
    "Avatar",
    "SectionTitle",
    "EmptyState",
    "Input",
    "TopBar",
  ]) {
    assert.match(crayonTsx, new RegExp(`export function ${name}\\b`));
  }
});

test("kid pages are not restyled yet", () => {
  const pages = [
    "app/learn/[studentId]/page.tsx",
    "app/learn/[studentId]/course/[courseId]/page.tsx",
    "app/learn-mobile/[studentId]/page.tsx",
    "app/learn-mobile/[studentId]/course/[courseId]/page.tsx",
    "app/kc-progress/page.tsx",
    "components/KcTutor.tsx",
    "components/KcCourseProgress.tsx",
    "components/learn/ChildHome.tsx",
    "components/learn/LearnMobileTutor.tsx",
  ];
  for (const page of pages) {
    const source = readFileSync(join(root, page), "utf8");
    assert.equal(source.includes("crayon"), false, page);
    assert.equal(source.includes("cb-"), false, page);
  }
});
