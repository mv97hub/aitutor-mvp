import fs from "node:fs";
import path from "node:path";

import { RECOMMENDATION_DOC } from "./harness-draft.ts";

export function writeRecommendationDoc(markdown: string): boolean {
  try {
    const dir = path.dirname(RECOMMENDATION_DOC);
    if (!fs.existsSync(dir)) return false;
    fs.writeFileSync(RECOMMENDATION_DOC, markdown);
    return true;
  } catch {
    return false;
  }
}
