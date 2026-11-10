import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

test("the administration bar puts creator links on the left and drops tutor shortcuts", () => {
  const menu = readFileSync(new URL("../components/admin/AdminMenu.tsx", import.meta.url), "utf8");
  const chats = menu.indexOf('label: "KC View Chats"');
  const config = menu.indexOf('label: "AI Tutor Configurations"');
  const course = menu.indexOf('label: "KC Course Creator"');
  const topic = menu.indexOf('label: "KC Topic Creator"');
  assert.ok(chats >= 0 && chats < config && config < course && course < topic);
  const nav = menu.slice(menu.indexOf("<nav"), menu.indexOf("</nav>"));
  const sections = nav.indexOf("VISIBLE_ADMIN_SECTIONS.map");
  const creators = nav.indexOf("CREATOR_LINKS.map");
  assert.ok(sections >= 0 && sections < creators);
  assert.match(menu, /href: "\/kc-studio"/);
  assert.match(menu, /href: "\/kc-creator"/);
  assert.doesNotMatch(menu, /KC Tutor|KC Progress|ds-admin-shortcuts|TOP_NAV_LINKS/);
});

test("creator pages omit learner links and name the topic creator", () => {
  const banner = readFileSync(new URL("../components/KcBanner.tsx", import.meta.url), "utf8");
  assert.match(banner, /learnerNav = true/);
  assert.match(banner, /\{learnerNav \?/);
  const links = banner.slice(banner.indexOf("LEARNER_BANNER_LINKS"), banner.indexOf("] as const"));
  assert.match(links, /Child Experience/);
  assert.match(links, /KC Tutor/);
  assert.match(links, /KC Course Progress/);

  const studio = readFileSync(new URL("../components/KcStudio.tsx", import.meta.url), "utf8");
  const creator = readFileSync(new URL("../components/KcCreator.tsx", import.meta.url), "utf8");
  const page = readFileSync(new URL("../app/kc-creator/page.tsx", import.meta.url), "utf8");
  assert.match(studio, /learnerNav=\{false\}/);
  assert.match(creator, /learnerNav=\{false\}/);
  assert.match(studio, /CreatorDebugButton/);
  assert.match(creator, /CreatorDebugButton/);
  assert.match(creator, /name="KC Topic Creator"/);
  assert.match(page, /title: "KC Topic Creator · AI Tutor"/);
  assert.doesNotMatch(creator, /name="KC Creator"/);
});

test("top navigation uses one quiet slate and no orange glow", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  const block = css.slice(css.indexOf("Quiet slate for top navigation"), css.indexOf("Full-width KC View Chats"));
  assert.ok(block.length > 0);
  assert.match(block, /background: #e8eef5/);
  assert.match(block, /color: #1e293b/);
  assert.match(block, /border: 1px solid #d2dce6/);
  assert.match(block, /box-shadow: none/);
  assert.match(block, /\.ds-top-btn:hover[\s\S]*background: #d5e0ec/);
  assert.match(block, /\.ds-top-btn\.is-active[\s\S]*background: #c5d3e3/);
  assert.match(block, /\.ds-top-btn\.is-on-banner\.is-active/);
  assert.doesNotMatch(block, /#f59e0b|#2563eb|#1e3a8a|box-shadow: 0/);
  assert.match(css, /\.button \{ background: var\(--teal\)/);
  assert.match(css, /button\.kc-primary \{ background: #0f6e6b/);
});
