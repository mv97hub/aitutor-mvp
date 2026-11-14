import { findingsOf, prepareDraft, recommendationMarkdown, type DraftMaterials } from "@/lib/harness-draft";
import { writeRecommendationDoc } from "@/lib/harness-draft-doc";
import { readModelUsage } from "@/lib/model-usage";

export const runtime = "nodejs";
export const maxDuration = 60;

const RECOMMENDATION_DOC_FLAG = "docs/harness-prompt-recommendations.md";

export async function POST(req: Request) {
  let body: DraftMaterials;
  try {
    body = (await req.json()) as DraftMaterials;
  } catch {
    return new Response("Expected JSON.", { status: 400 });
  }
  const prepared = prepareDraft(body);
  const cards = prepared.cards;
  const materials = prepared.materials;
  if (cards.length === 0) {
    const findings = findingsOf(materials);
    const several = (materials.run_id || "").includes(",");
    if (findings.length === 0) {
      return new Response(
        several ? "The selected runs have no findings, so there is nothing to draft." : "This run has no findings, so there is nothing to draft.",
        { status: 422 },
      );
    }
    return new Response(
      several
        ? "The selected runs have no stored turn to quote, so no observation was drafted."
        : "This run has no stored turn to quote, so no observation was drafted.",
      { status: 422 },
    );
  }
  const runId = String(materials.run_id || body.run_id || "");
  const wrote = writeRecommendationDoc(recommendationMarkdown(runId, cards));
  return Response.json({
    cards,
    usage: readModelUsage(undefined),
    judge_model: "",
    drafter: "observations",
    recommendations_doc: wrote ? RECOMMENDATION_DOC_FLAG : "",
  });
}
