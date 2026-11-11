import type { KcBlueprint, KcCoverage, KcStatement } from "./kc.ts";

/** The curricula the intake form can align a course to. None is the empty id. */
export const CURRICULA = [
  { id: "", label: "None", site: "", host: "" },
  {
    id: "common_core_math",
    label: "Common Core (math)",
    site: "https://www.corestandards.org/Math/",
    host: "corestandards.org",
  },
  {
    id: "common_core_ela",
    label: "Common Core (ELA)",
    site: "https://www.corestandards.org/ELA-Literacy/",
    host: "corestandards.org",
  },
  { id: "ngss", label: "NGSS", site: "https://www.nextgenscience.org/", host: "nextgenscience.org" },
  { id: "uk", label: "UK National Curriculum", site: "https://www.gov.uk/national-curriculum", host: "gov.uk" },
  {
    id: "australian",
    label: "Australian Curriculum",
    site: "https://www.australiancurriculum.edu.au/",
    host: "australiancurriculum.edu.au",
  },
  { id: "ontario", label: "Ontario", site: "https://www.dcp.edu.gov.on.ca/en/curriculum", host: "dcp.edu.gov.on.ca" },
  {
    id: "ib_pyp",
    label: "International Baccalaureate PYP",
    site: "https://www.ibo.org/programmes/primary-years-programme/",
    host: "ibo.org",
  },
  { id: "other", label: "Other", site: "", host: "" },
] as const;

/** A sample the author can copy. It is not a real course. */
export const STANDARD_EXAMPLE = [
  "3.NF.A.1 Understand a fraction 1/b as the quantity formed by 1 part when a whole is partitioned into b equal parts.",
  "3.NF.A.2 Understand a fraction as a number on the number line.",
  "3.NF.A.3 Explain equivalence of fractions and compare fractions by reasoning about their size.",
].join("\n");

export function curriculumOf(id: string) {
  return CURRICULA.find((item) => item.id === id) ?? CURRICULA[0];
}

/** Statements down the side, components across. A code on one component is only touched lightly. */
export function coverageOf(statements: KcStatement[], blueprint: KcBlueprint | null): KcCoverage {
  const components = (blueprint?.units ?? []).flatMap((unit) => unit.components);
  const rows = statements.map((statement) => {
    const covering = components
      .filter((item) => (item.standards ?? []).includes(statement.code) && item.code)
      .map((item) => item.code);
    const status = covering.length === 0 ? "missing" : covering.length === 1 ? "light" : "covered";
    return {
      code: statement.code,
      text: statement.text,
      components: covering,
      status,
      once_without_review: status === "light",
    } as const;
  });
  return {
    rows: [...rows],
    gaps: rows.filter((row) => row.status === "missing").map((row) => row.code),
    light: rows.filter((row) => row.status === "light").map((row) => row.code),
    once_without_review: rows.filter((row) => row.once_without_review).map((row) => row.code),
    extensions: statements.length
      ? components.filter((item) => item.code && !(item.standards ?? []).length).map((item) => item.code)
      : [],
  };
}
