"use server";

import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import type { KcCourse } from "@/lib/kc";
import { draftKcComponent } from "@/lib/kc-draft";
import { kcModel } from "@/lib/kc-models";
import { KcDraftError, promptTurnId, rememberCreatorPrompts } from "@/lib/kc-prompt-log";

function bounce(path: string, error: unknown): never {
  const message = error instanceof Error ? error.message : "That did not save.";
  const join = path.includes("?") ? "&" : "?";
  redirect(`${path}${join}error=${encodeURIComponent(message)}`);
}

function minutesOf(formData: FormData): number | null {
  const raw = String(formData.get("minutes") || "").trim();
  return raw ? Number(raw) : null;
}

function intakeOf(formData: FormData) {
  const count = String(formData.get("component_count") || "").trim();
  const text = (name: string) => String(formData.get(name) || "").trim();
  return {
    reading_level: text("reading_level") || "age",
    depth: text("depth") || "standard",
    component_count: count ? Number(count) : null,
    align_syllabus: formData.get("align_syllabus") === "yes",
    use: text("use"),
    standard: text("standard"),
    standard_grade: text("standard_grade"),
    standard_name: text("standard_name"),
    standard_text: text("standard_text"),
    starting_point: text("starting_point"),
    must_cover: text("must_cover"),
    must_avoid: text("must_avoid"),
    interests: text("interests"),
    misconceptions_seen: text("misconceptions_seen"),
    source_text: text("source_text"),
    source_text_cut: formData.get("source_text_cut") === "yes",
    standard_text_cut: formData.get("standard_text_cut") === "yes",
  };
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
  const sourceText = String(formData.get("source_text") || "").trim();
  try {
    created = await api<KcCourse>("/kc/courses", {
      method: "POST",
      body: JSON.stringify({
        title: String(formData.get("title") || ""),
        description: String(formData.get("description") || ""),
        audience: String(formData.get("audience") || "12-14"),
        kind: String(formData.get("kind") || "mastery"),
        minutes: minutesOf(formData),
        ...(sourceText ? { intake: { source_text: sourceText } } : {}),
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
        intake: intakeOf(formData),
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

function creatorReadyBack(formData: FormData) {
  const courseId = String(formData.get("course_id") || "");
  const nodeId = String(formData.get("node_id") || "").trim();
  const raw = String(formData.get("model") || "").trim();
  const params = new URLSearchParams();
  params.set("course", courseId);
  if (nodeId) params.set("kc", nodeId);
  if (raw) params.set("model", kcModel(raw));
  return `/kc-creator?${params.toString()}`;
}

export async function markKcCourseReady(formData: FormData) {
  const back = creatorReadyBack(formData);
  const courseId = String(formData.get("course_id") || "");
  try {
    await api(`/kc/courses/${courseId}/ready`, { method: "POST" });
  } catch (error) {
    bounce(back, error);
  }
  redirect(back);
}

export async function deleteKcUnit(formData: FormData) {
  const courseId = String(formData.get("course_id") || "");
  const unitIndex = String(formData.get("unit_index") || "");
  const chat = String(formData.get("mode") || "") === "chat";
  const back = `/kc-studio?course=${courseId}${chat ? "&mode=chat" : ""}`;
  try {
    await api(`/kc/courses/${courseId}/units/${unitIndex}`, { method: "DELETE" });
  } catch (error) {
    bounce(back, error);
  }
  redirect(back);
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
  const message = String(formData.get("message") || "");
  const back = `/kc-creator?course=${courseId}&kc=${nodeId}&model=${encodeURIComponent(model)}`;
  const turnId = promptTurnId([nodeId, message, String(Date.now()), String(Math.random())]);
  try {
    const allowed = String(formData.get("allowed_block_types") || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const prompts = await draftKcComponent({
      nodeId,
      message,
      model,
      allowedBlockTypes: allowed,
    });
    rememberCreatorPrompts(nodeId, { id: turnId, prompts });
  } catch (error) {
    if (error instanceof KcDraftError && error.prompts.length > 0) {
      rememberCreatorPrompts(nodeId, { id: turnId, prompts: error.prompts });
    }
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

function blocksOf(formData: FormData): unknown[] {
  const raw = String(formData.get("blocks") || "").trim();
  if (!raw) return [];
  const parsed = JSON.parse(raw) as unknown;
  if (!Array.isArray(parsed)) throw new Error("Blocks must be a list.");
  return parsed;
}

export async function saveKcBlockScope(formData: FormData) {
  const courseId = String(formData.get("course_id") || "");
  const nodeId = String(formData.get("node_id") || "");
  const back =
    String(formData.get("return_to") || "") === "studio"
      ? `/kc-studio?course=${courseId}${formData.get("model") ? `&model=${encodeURIComponent(String(formData.get("model")))}` : ""}`
      : creatorBack(courseId, nodeId, formData);
  const allowed = formData.getAll("allowed_block_types").map(String);
  try {
    await api(`/kc/courses/${courseId}`, {
      method: "PATCH",
      body: JSON.stringify({ allowed_block_types: allowed.length ? allowed : ["topic_goal"] }),
    });
  } catch (error) {
    bounce(back, error);
  }
  redirect(back);
}

export async function saveKcComponent(formData: FormData) {
  const courseId = String(formData.get("course_id") || "");
  const nodeId = String(formData.get("node_id") || "");
  const back = creatorBack(courseId, nodeId, formData);
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
        outline: String(formData.get("outline") || ""),
        core_truth: String(formData.get("core_truth") || ""),
        misconceptions,
        prerequisite_codes: formData.getAll("prerequisite_codes").map(String),
        encompasses_codes: formData.getAll("encompasses_codes").map(String),
        blocks: blocksOf(formData),
      }),
    });
  } catch (error) {
    bounce(back, error);
  }
  redirect(back);
}

