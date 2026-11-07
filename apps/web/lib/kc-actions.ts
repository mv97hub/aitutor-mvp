"use server";

import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import type { KcCourse } from "@/lib/kc";
import { draftKcComponent } from "@/lib/kc-draft";
import { kcModel } from "@/lib/kc-models";

function bounce(path: string, error: unknown): never {
  const message = error instanceof Error ? error.message : "That did not save.";
  const join = path.includes("?") ? "&" : "?";
  redirect(`${path}${join}error=${encodeURIComponent(message)}`);
}

function minutesOf(formData: FormData): number | null {
  const raw = String(formData.get("minutes") || "").trim();
  return raw ? Number(raw) : null;
}

function creatorBack(courseId: string, nodeId: string, formData: FormData) {
  const raw = String(formData.get("model") || "").trim();
  const params = new URLSearchParams();
  params.set("course", courseId);
  params.set("kc", nodeId);
  if (raw) params.set("model", kcModel(raw));
  return `/kc-creator?${params.toString()}`;
}

export async function createKcCourse(formData: FormData) {
  let created: KcCourse | null = null;
  try {
    created = await api<KcCourse>("/kc/courses", {
      method: "POST",
      body: JSON.stringify({
        title: String(formData.get("title") || ""),
        description: String(formData.get("description") || ""),
        audience: String(formData.get("audience") || "12-14"),
        kind: String(formData.get("kind") || "mastery"),
        minutes: minutesOf(formData),
      }),
    });
  } catch (error) {
    bounce("/kc-studio", error);
  }
  redirect(`/kc-studio?course=${created?.id}`);
}

export async function saveKcCourse(formData: FormData) {
  const courseId = String(formData.get("course_id") || "");
  try {
    await api(`/kc/courses/${courseId}`, {
      method: "PATCH",
      body: JSON.stringify({
        title: String(formData.get("title") || ""),
        description: String(formData.get("description") || ""),
        audience: String(formData.get("audience") || "12-14"),
        kind: String(formData.get("kind") || "mastery"),
        minutes: minutesOf(formData),
      }),
    });
  } catch (error) {
    bounce(`/kc-studio?course=${courseId}`, error);
  }
  redirect(`/kc-studio?course=${courseId}`);
}

export async function markKcReady(formData: FormData) {
  const courseId = String(formData.get("course_id") || "");
  try {
    await api(`/kc/courses/${courseId}/ready`, { method: "POST" });
  } catch (error) {
    bounce(`/kc-studio?course=${courseId}`, error);
  }
  redirect(`/kc-studio?course=${courseId}`);
}

export async function pushKcDraft(formData: FormData) {
  const courseId = String(formData.get("course_id") || "");
  try {
    const components = JSON.parse(String(formData.get("components") || "[]")) as unknown[];
    await api(`/kc/courses/${courseId}/push`, {
      method: "POST",
      body: JSON.stringify({ components }),
    });
  } catch (error) {
    bounce(`/kc-studio?course=${courseId}`, error);
  }
  redirect(`/kc-studio?course=${courseId}`);
}

export async function pushKcComponent(formData: FormData) {
  const courseId = String(formData.get("course_id") || "");
  const nodeId = String(formData.get("node_id") || "");
  const back = creatorBack(courseId, nodeId, formData);
  try {
    const payload = JSON.parse(String(formData.get("payload") || "{}")) as Record<string, unknown>;
    await api(`/kc/nodes/${nodeId}/push`, { method: "POST", body: JSON.stringify(payload) });
  } catch (error) {
    bounce(back, error);
  }
  redirect(back);
}

export async function postKcCreatorMessage(formData: FormData) {
  const courseId = String(formData.get("course_id") || "");
  const nodeId = String(formData.get("node_id") || "");
  const model = kcModel(String(formData.get("model") || ""));
  const back = `/kc-creator?course=${courseId}&kc=${nodeId}&model=${encodeURIComponent(model)}`;
  try {
    await draftKcComponent({
      nodeId,
      message: String(formData.get("message") || ""),
      model,
    });
  } catch (error) {
    bounce(back, error);
  }
  redirect(back);
}

export async function markKcComplete(formData: FormData) {
  const courseId = String(formData.get("course_id") || "");
  const nodeId = String(formData.get("node_id") || "");
  const back = creatorBack(courseId, nodeId, formData);
  try {
    await api(`/kc/nodes/${nodeId}/complete`, { method: "POST" });
  } catch (error) {
    bounce(back, error);
  }
  redirect(back);
}

export async function addKcComponent(formData: FormData) {
  const courseId = String(formData.get("course_id") || "");
  try {
    await api(`/kc/courses/${courseId}/components`, {
      method: "POST",
      body: JSON.stringify({ title: String(formData.get("title") || "") }),
    });
  } catch (error) {
    bounce(`/kc-studio?course=${courseId}`, error);
  }
  redirect(`/kc-studio?course=${courseId}`);
}

export async function moveKcComponent(formData: FormData) {
  const courseId = String(formData.get("course_id") || "");
  const id = String(formData.get("id") || "");
  const direction = Number(formData.get("direction") || 0);
  const ids = formData.getAll("order").map(String);
  const index = ids.indexOf(id);
  const next = index + direction;
  if (index >= 0 && next >= 0 && next < ids.length) {
    const swapped = [...ids];
    const [item] = swapped.splice(index, 1);
    swapped.splice(next, 0, item!);
    try {
      await api(`/kc/courses/${courseId}/reorder`, {
        method: "POST",
        body: JSON.stringify({ ids: swapped }),
      });
    } catch (error) {
      bounce(`/kc-studio?course=${courseId}`, error);
    }
  }
  redirect(`/kc-studio?course=${courseId}`);
}

export async function removeKcComponent(formData: FormData) {
  const courseId = String(formData.get("course_id") || "");
  const id = String(formData.get("id") || "");
  try {
    await api(`/kc/nodes/${id}`, { method: "DELETE" });
  } catch (error) {
    bounce(`/kc-studio?course=${courseId}`, error);
  }
  redirect(`/kc-studio?course=${courseId}`);
}

function typeFields(kcType: string, formData: FormData): Record<string, unknown> {
  const text = (key: string) => String(formData.get(key) || "");
  if (kcType === "procedural") {
    return {
      steps: text("steps")
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      blanked_step: Number(text("blanked_step") || 0),
      solo_problem: text("solo_problem"),
      solo_check: text("solo_check"),
    };
  }
  if (kcType === "synthesis") {
    return {
      mixes: [text("mix_a"), text("mix_b")].filter(Boolean),
      faulty_plan: text("faulty_plan"),
    };
  }
  if (kcType === "conceptual") {
    return {
      case_a: text("case_a"),
      case_b: text("case_b"),
      prediction: text("prediction"),
      rule: text("rule"),
      transfer_case: text("transfer_case"),
    };
  }
  if (kcType === "causal") {
    return {
      decision_point: text("decision_point"),
      flawed_claim: text("flawed_claim"),
      causal_chain: text("causal_chain"),
      counterfactual: text("counterfactual"),
    };
  }
  return { fact: text("fact"), retrieval_question: text("retrieval_question") };
}

export async function saveKcComponent(formData: FormData) {
  const courseId = String(formData.get("course_id") || "");
  const nodeId = String(formData.get("node_id") || "");
  const back = creatorBack(courseId, nodeId, formData);
  const kcType = String(formData.get("kc_type") || "factual");
  const wrong = formData.getAll("wrong_move").map(String);
  const broken = formData.getAll("broken_kc").map(String);
  const misconceptions = wrong
    .map((move, index) => ({ wrong_move: move.trim(), broken_kc: (broken[index] || "").trim() }))
    .filter((item) => item.wrong_move && item.broken_kc);
  try {
    await api(`/kc/nodes/${nodeId}`, {
      method: "PUT",
      body: JSON.stringify({
        title: String(formData.get("title") || ""),
        description: String(formData.get("description") || ""),
        kc_type: kcType,
        core_truth: String(formData.get("core_truth") || ""),
        rubric: formData
          .getAll("rubric")
          .map((item) => String(item).trim())
          .filter(Boolean),
        misconceptions,
        prerequisite_codes: formData.getAll("prerequisite_codes").map(String),
        encompasses_codes: formData.getAll("encompasses_codes").map(String),
        type_fields: typeFields(kcType, formData),
      }),
    });
  } catch (error) {
    bounce(back, error);
  }
  redirect(back);
}

