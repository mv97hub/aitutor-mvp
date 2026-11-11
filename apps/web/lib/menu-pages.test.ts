import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { knownStudentId, menuSections, menuSectionsFor } from "./menu-pages.ts";

const previousDestinations = [
  ["/admin", "Admin"],
  ["/admin/agent-customizations", "AI Tutor Configurations"],
  ["/kc-studio", "KC Course Creator"],
  ["/manage-kc-courses", "Manage KC courses"],
  ["/kc-creator", "KC Topic Creator"],
  ["/kc-tutor", "KC Tutor"],
  ["/kc-prompt-tester", "KC Prompt Tester"],
  ["/kc-progress", "Detailed Progress"],
  ["/viewkcchats", "View KC chats"],
  ["/documentation", "Documentation"],
  ["/", "Home"],
  ["/create-course", "Create course"],
  ["/manage-courses", "Manage courses"],
  ["/viewchats", "View chats"],
  ["/learn-mobile", "Mobile child"],
  ["/parent", "Parent portal"],
] as const;

test("menu sections keep every destination under the six headers", () => {
  assert.deepEqual(
    menuSections.map((section) => section.title),
    ["Kids Portal", "Parent Portal", "Administration", "KC course creation", "Testing pages", "Deprecated Pages"],
  );

  const links = menuSections.flatMap((section) => section.links.map((link) => [link.href, link.label]));
  for (const [href, label] of previousDestinations) {
    assert.ok(
      links.some((link) => link[0] === href && link[1] === label),
      `${label} ${href} stays on the menu`,
    );
  }

  const byTitle = Object.fromEntries(
    menuSections.map((section) => [section.title, section.links.map((link) => [link.label, link.href])]),
  );
  assert.deepEqual(byTitle["Kids Portal"], [
    ["Child chooser", "/learn"],
    ["Mobile child", "/learn-mobile"],
  ]);
  assert.deepEqual(byTitle["Parent Portal"], [["Parent portal", "/parent"]]);
  assert.equal(
    menuSections.findIndex((section) => section.title === "Parent Portal"),
    menuSections.findIndex((section) => section.title === "Kids Portal") + 1,
  );
  assert.deepEqual(byTitle["Administration"], [
    ["Admin", "/admin"],
    ["KC View Chats", "/admin/kc-chats"],
    ["View KC chats", "/viewkcchats"],
    ["AI Tutor Configurations", "/admin/agent-customizations"],
    ["AI Safety", "/admin/ai-safety"],
    ["Token usage", "/admin/token-usage"],
    ["Documentation", "/documentation"],
  ]);
  assert.deepEqual(byTitle["KC course creation"], [
    ["KC Course Creator", "/kc-studio"],
    ["KC Topic Creator", "/kc-creator"],
    ["Manage KC courses", "/manage-kc-courses"],
  ]);
  assert.deepEqual(byTitle["Testing pages"], [
    ["KC Tutor", "/kc-tutor"],
    ["KC Prompt Tester", "/kc-prompt-tester"],
    ["Detailed Progress", "/kc-progress"],
  ]);
  assert.equal(
    byTitle["Testing pages"].findIndex((link) => link[0] === "KC Prompt Tester"),
    byTitle["Testing pages"].findIndex((link) => link[0] === "KC Tutor") + 1,
  );
  assert.deepEqual(byTitle["Deprecated Pages"], [
    ["Lesson Desk", "/admin/lessons"],
    ["Home", "/"],
    ["Create course", "/create-course"],
    ["Manage courses", "/manage-courses"],
    ["View chats", "/viewchats"],
  ]);
  assert.equal(
    menuSections.find((section) => section.title === "Deprecated Pages")?.links.some((link) => link.href === "/kc-progress"),
    false,
  );
});

test("child home is linked only when a student id is already known", () => {
  assert.equal(knownStudentId(undefined), null);
  assert.equal(knownStudentId("  "), null);
  assert.equal(knownStudentId("not-a-student"), null);
  const id = "11111111-2222-3333-4444-555555555555";
  assert.equal(knownStudentId(`  ${id}  `), id);

  assert.deepEqual(
    menuSectionsFor(null)[0].links.map((link) => link.href),
    ["/learn", "/learn-mobile"],
  );
  assert.deepEqual(
    menuSectionsFor("sam")[0].links.map((link) => [link.label, link.href]),
    [
      ["Child chooser", "/learn"],
      ["Mobile child", "/learn-mobile"],
    ],
  );
  assert.deepEqual(
    menuSectionsFor(id)[0].links.map((link) => [link.label, link.href]),
    [
      ["Child chooser", "/learn"],
      ["Mobile child", "/learn-mobile"],
      ["Child home", `/learn/${id}`],
    ],
  );
  assert.equal(menuSectionsFor(id).length, menuSections.length);
});

test("the learner header links to the child experience and keeps creator and admin off it", () => {
  const banner = readFileSync(new URL("../components/KcBanner.tsx", import.meta.url), "utf8");
  const links = banner.slice(banner.indexOf("LEARNER_BANNER_LINKS"), banner.indexOf("] as const"));
  assert.match(links, /href: "\/learn"/);
  assert.match(links, /Child Experience/);
  assert.doesNotMatch(links, /Course Creator|\/admin|\/kc-creator|\/kc-studio/);
});
