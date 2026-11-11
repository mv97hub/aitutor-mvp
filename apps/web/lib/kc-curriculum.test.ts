import assert from "node:assert/strict";
import test from "node:test";

import { PASTE_LIMIT, PASTE_OVERRIDE_NOTE, intakeCutNotes, pasteOverridesDepth, pastedCurriculumCount } from "./kc-curriculum.ts";

test("a longer paste overrides Standard depth and a cut is noted", () => {
  const lines = [];
  for (let index = 1; index <= 42; index += 1) {
    lines.push(`Unit ${index}: Topic ${index}`);
    lines.push(`${index}. Topic ${index} about scarcity and choice.`);
  }
  const count = pastedCurriculumCount("", lines.join("\n"));
  assert.equal(count, 42);
  assert.equal(pasteOverridesDepth("standard", count), true);
  assert.equal(pasteOverridesDepth("standard", 12), false);
  assert.equal(pasteOverridesDepth("intro", 7), true);
  assert.equal(pasteOverridesDepth("curriculum", 42), false);
  assert.match(PASTE_OVERRIDE_NOTE, /overrides Standard depth/);
  assert.deepEqual(intakeCutNotes({ source_text_cut: true, standard_text_cut: true }).length, 2);
  assert.match(intakeCutNotes({ source_text_cut: true })[0] ?? "", /100,000/);
  assert.equal(PASTE_LIMIT, 100_000);
  assert.equal(pastedCurriculumCount("", "A prose source with no unit headers."), 0);
});

const AP_MACRO = `Unit 1: Basic Economic Concepts
* 1.1 Scarcity
* 1.2 Opportunity Cost and the Production Possibilities Curve (PPC)
* 1.3 Comparative Advantage and Gains from Trade
* 1.4 Demand
* 1.5 Supply
* 1.6 Market Equilibrium, Disequilibrium, and Changes in Equilibrium
Unit 2: Economic Indicators and the Business Cycle
* 2.1 The Circular Flow and GDP
* 2.2 Limitations of GDP
* 2.3 Unemployment
* 2.4 Price Indices and Inflation
* 2.5 Costs of Inflation
* 2.6 Real v. Nominal GDP
* 2.7 Business Cycles
Unit 3: National Income and Price Determination
* 3.1 Aggregate Demand (AD)
* 3.2 Multipliers
* 3.3 Short-Run Aggregate Supply (SRAS)
* 3.4 Long-Run Aggregate Supply (LRAS)
* 3.5 Equilibrium in the AD-AS Model
* 3.6 Changes in the AD-AS Model in the Short Run
* 3.7 Long-Run Self-Adjustment
* 3.8 Fiscal Policy
* 3.9 Automatic Stabilizers
Unit 4: Financial Sector
* 4.1 Financial Assets
* 4.2 Nominal v. Real Interest Rates
* 4.3 Definition, Measurement, and Functions of Money
* 4.4 Banking and the Expansion of the Money Supply
* 4.5 The Money Market
* 4.6 Monetary Policy
* 4.7 The Loanable Funds Market
Unit 5: Long-Run Consequences of Stabilization Policies
* 5.1 Fiscal and Monetary Policy Actions in the Short Run
* 5.2 The Phillips Curve
* 5.3 Money Growth and Inflation
* 5.4 Government Deficits and the National Debt
* 5.5 Crowding Out
* 5.6 Economic Growth
* 5.7 Public Policy and Economic Growth
Unit 6: Open Economy—International Trade and Finance
* 6.1 Balance of Payments Accounts
* 6.2 Exchange Rates
* 6.3 The Foreign Exchange Market
* 6.4 Effect of Changes in Policies and Economic Conditions on the Foreign Exchange Market
* 6.5 Changes in the Foreign Exchange Market and Net Exports
* 6.6 Real Interest Rates and International Capital Flows
`;

test("an AP Macro outline counts the numbered topics, and a flat list counts without unit headers", () => {
  assert.equal(pastedCurriculumCount("", AP_MACRO), 42);
  const flat = Array.from({ length: 13 }, (_, index) => `- Topic ${index + 1} about scarcity and choice.`).join("\n");
  assert.equal(pastedCurriculumCount("", flat), 13);
  assert.equal(pastedCurriculumCount("", flat, { alignSyllabus: true }), 13);
  assert.equal(pastedCurriculumCount("", flat, { depth: "curriculum" }), 13);
  const weeks = Array.from({ length: 13 }, (_, index) => `Week ${index + 1}: Topic ${index + 1} about scarcity.`).join("\n");
  assert.equal(pastedCurriculumCount("", weeks), 13);
  const numbered = Array.from({ length: 42 }, (_, index) => `${index + 1}. Topic ${index + 1} about scarcity and choice.`).join("\n");
  assert.equal(pastedCurriculumCount("", numbered), 42);
  assert.equal(pastedCurriculumCount("", "- Only one topic about scarcity."), 0);
  const topics = Array.from({ length: 42 }, (_, index) => `Topic 1.${index + 1} Idea ${index + 1} about scarcity and choice.`).join("\n");
  assert.equal(pastedCurriculumCount("", topics), 42);
  const bullets = ["– 1.1 Scarcity", "— 1.2 Opportunity cost", "· 1.3 Comparative advantage"].join("\n");
  assert.equal(pastedCurriculumCount("", bullets), 3);
});
