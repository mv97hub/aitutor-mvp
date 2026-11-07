import assert from "node:assert/strict";
import test from "node:test";

import { kcAndAdminPages, olderPages } from "./menu-pages.ts";

test("KC and admin links sit above the older pages, with Course Progress in the top group", () => {
  assert.deepEqual(
    kcAndAdminPages.map((page) => page.label),
    [
      "Admin",
      "Agent customizations",
      "KC Course Creator",
      "Manage KC courses",
      "KC Creator",
      "KC Tutor",
      "KC Course Progress",
      "View KC chats",
      "Documentation",
    ],
  );
  assert.equal(kcAndAdminPages.find((page) => page.label === "KC Course Progress")?.href, "/kc-progress");
  assert.deepEqual(
    olderPages.map((page) => page.label),
    ["Home", "Create course", "Manage courses", "View chats"],
  );
  assert.equal(
    olderPages.some((page) => page.href === "/kc-progress"),
    false,
  );
});
