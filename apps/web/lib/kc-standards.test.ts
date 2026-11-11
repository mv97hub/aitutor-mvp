import assert from "node:assert/strict";
import test from "node:test";

import type { KcBlueprint } from "./kc.ts";
import { coverageOf, CURRICULA, STANDARD_EXAMPLE } from "./kc-standards.ts";

test("the picker names each official site and the sample is the fractions list", () => {
  const hosts = Object.fromEntries(CURRICULA.map((item) => [item.id, item.host]));
  assert.equal(hosts[""], "");
  assert.equal(hosts.common_core_math, "corestandards.org");
  assert.equal(hosts.common_core_ela, "corestandards.org");
  assert.equal(hosts.ngss, "nextgenscience.org");
  assert.equal(hosts.uk, "gov.uk");
  assert.equal(hosts.australian, "australiancurriculum.edu.au");
  assert.equal(hosts.ontario, "dcp.edu.gov.on.ca");
  assert.equal(hosts.ib_pyp, "ibo.org");
  assert.equal(hosts.other, "");
  assert.match(STANDARD_EXAMPLE, /^3\.NF\.A\.1 Understand a fraction 1\/b/);
  assert.match(STANDARD_EXAMPLE, /3\.NF\.A\.2 Understand a fraction as a number on the number line\./);
  assert.match(STANDARD_EXAMPLE, /3\.NF\.A\.3 Explain equivalence of fractions/);
  assert.equal(STANDARD_EXAMPLE.split("\n").length, 3);
});

test("five statements report a missing one and an uncovered component is an extension", () => {
  const statements = ["3.NF.A.1", "3.NF.A.2", "3.NF.A.3", "3.NF.A.4", "3.NF.A.5"].map((code) => ({
    code,
    text: `Statement ${code}`,
  }));
  const blueprint: KcBlueprint = {
    outcomes: ["One."],
    units: [
      {
        title: "Fractions",
        summary: "A unit.",
        components: [
          { code: "part", title: "Parts", summary: "A.", prerequisites: [], standards: ["3.NF.A.1", "3.NF.A.2"] },
          { code: "line", title: "Line", summary: "B.", prerequisites: ["part"], standards: ["3.NF.A.3"] },
          { code: "size", title: "Size", summary: "C.", prerequisites: ["line"], standards: ["3.NF.A.4"] },
          { code: "again", title: "Again", summary: "D.", prerequisites: ["size"], standards: ["3.NF.A.4"] },
          { code: "extra", title: "Extra", summary: "E.", prerequisites: ["again"], standards: [] },
        ],
      },
    ],
  };
  const coverage = coverageOf(statements, blueprint);
  assert.deepEqual(coverage.gaps, ["3.NF.A.5"]);
  assert.deepEqual(coverage.extensions, ["extra"]);
  assert.deepEqual(coverage.light, ["3.NF.A.1", "3.NF.A.2", "3.NF.A.3"]);
  assert.equal(coverage.rows.find((row) => row.code === "3.NF.A.4")?.status, "covered");
  assert.equal(coverage.rows.find((row) => row.code === "3.NF.A.5")?.once_without_review, false);
  assert.equal(coverage.rows.find((row) => row.code === "3.NF.A.3")?.once_without_review, true);
});
