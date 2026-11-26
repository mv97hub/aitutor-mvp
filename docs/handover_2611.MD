# Handover for 26 November 2026

This file is a brief for Codex. It is not an analysis of the test run. Do not treat any sentence below as a finding until you have read the downloaded run and the code it names.

The reader pastes this file into Codex together with the downloaded run. Codex then checks the run against the GitHub repo and writes recommendations. Do not call the tutor model. Do not start a new harness run. Do not change production data.

Overarching rule for every recommendation: keep the code as simple as is feasible, and still give the child a best-in-class tutor. Prefer one clear path over a new layer, a new flag, or a new prompt section. A change earns its place only when a real child turn in this run is worse without it.

## Get the run first

1. Open https://aitutor-mvp-web.onrender.com/kc-test-children
2. Open the **Runs** tab.
3. Find the run from **26 November 2026** that contains **56** chats.
4. Download that run. The Runs tab button saves one markdown file for the whole run (`harness-run-<id>.md`). That file is the only transcript source. Do not use an older 56-chat export. A previous 56-chat run exists from 15 November 2026 and is not this job.
5. If several runs on 26 November show 56 chats, use the latest finished one. Record its id, created time, tutor models, and child names in the first paragraph of your answer.
6. Keep the download next to the repo. Read it locally. Do not re-download inside the analysis unless the file is truncated.

The download is produced by `GET /kc/harness/runs/{id}/download` (`apps/api/app/harness_download.py`). It keeps every stored turn, including a blank or failed tutor call, plus checks, scores, and the model record.

## Repo to read

GitHub: https://github.com/mv97hub/aitutor-mvp

Read `main`. The product that the harness drives is the knowledge-component tutor, not the older quest chat, unless a turn in the download is clearly the quest tutor.

| Area | Start here |
| --- | --- |
| Session and turn | `apps/api/app/kc.py` |
| What the loop decides | `apps/api/app/kc_loop.py` (`resolve_block_turn`, `forecast_this_turn`) |
| What a finished block records | `apps/api/app/block_score.py` |
| Prompt text | `apps/api/app/kc_prompt.py` |
| Prompt excerpts the harness can point at | `apps/api/app/harness_prompt_source.py` |
| Passage-only checks | `apps/api/app/kc_blocks.py` |
| Block types and tutor config defaults | `apps/api/app/models.py` (`ALL_BLOCK_TYPES`, `default_kc_tutor_config`, `effective_child_profile`) |
| Child and tutor profile normalization | `apps/api/app/tutor_profile.py` |
| Stars | `apps/api/app/learn_stars.py` |
| Quest tutor (only if the run uses it) | `apps/api/app/engine/assemble.py`, `apps/api/app/prompt_loader.py` |
| Harness runner, children, checks | `apps/api/app/harness.py`, `apps/api/app/harness_personas.py`, `apps/api/app/harness_checks.py`, `apps/api/app/harness_report.py` |
| Child reply the harness sends | `apps/web/lib/harness-runner.ts`, `apps/web/app/api/kc/harness/` |
| Runs screen | `apps/web/components/harness/RunsTab.tsx`, `apps/web/app/kc-test-children/page.tsx` |
| Authoring guide | `apps/web/app/documentation/kc-prompt-layers/page.tsx`, `apps/web/app/documentation/kc-tutor/page.tsx`, `apps/web/components/docs/BlockCloseFlow.tsx` |

The KC prompt is seven sections, in this order: This turn, What to teach, Who you are talking to, How to teach, How to sound, What just happened, What to return. Later blocks in the component are not sent on a middle turn.

Block types: `topic_goal`, `mcq`, `case_study`, `socratic`, `curiosity`, `worked_example`, `spot_the_flaw`, `teach_back`, `retrieval_check`, `explanation`, `passage_ela`.

Named harness children live in `starter_children()` in `apps/api/app/harness_personas.py` (`AI_Child1` through `AI_Child14`). Each child has an age, a `child_profile`, and numeric `traits`.

## How to analyze

Work in this order. Quote the child line and the tutor line. Name the chat id, the child, the block type, and the substep. Then name the function that decided the step, or say that the model spoke against a decision the loop already made.

1. Count the run: chats, finished versus stuck, tutors, children, block types that actually appear.
2. Read every stuck chat turn by turn. Then sample completed chats until each block type that appears has at least one clean chat and one troubled chat, if both exist.
3. For each bad turn, separate three causes. Do not blend them.
   - The loop chose the wrong next step (`resolve_block_turn` in `kc_loop.py`).
   - The loop chose the right step, and the prompt told the model to say the wrong thing (`kc_prompt.py`).
   - The loop and the prompt were right, and the stored reply is the previous turn again, a blank call, or a harness write (`harness.py`, `apps/web/lib/harness-runner.ts`).
4. Check the requirement score only when `scoring_version` is 2. Version 2 records known, fragile, or unassessed from requirements. Forecast is a preview. It must not be treated as the committed verdict (`block_score.py`).
5. Check the child the harness pretended to be. Compare the spoken child line with that child's age, `child_profile`, and `traits`. A line that no child with those settings would say is a harness miss, not a tutor miss.
6. After the turns are grouped, write recommendations. Every recommendation names the file, the behavior to change, the child turn that justifies it, and the behavior to leave alone.

Ignore a one-off line unless the same shape shows up in more than one chat. "What's next?" while the goal question is still open is not, by itself, a tutor failure.

## What to return

Group the recommendations under the headings below. Under each heading, put one **Priority** first. The priority is the single change that helps the child most in this run without a new subsystem. After it, list only the other changes that the run supports. If the run does not support a heading, say so and do not invent a change.

For each recommendation use this shape:

- **Change.** One sentence.
- **Why this run.** Chat id, child, block, substep, the child line, the tutor line.
- **Where.** File and function.
- **Simpler alternative rejected.** What you considered adding, and why the smaller change is enough.
- **Leave alone.** The nearby behavior that already works and must not be rewritten.

---

## Prompt: architecture

Read `apps/api/app/kc.py`, `kc_loop.py`, `block_score.py`, and `kc_prompt.py` as one turn, not four products.

Ask:

- Where does one child line get two decisions (a loop outcome and a model speech that disagree)?
- Where does a new session pin `scoring_version`, and where would a mid-session change be a mistake?
- Which path still belongs to the quest tutor (`engine/assemble.py`) and must not be folded into the KC tutor?
- What is the smallest place for a new child-facing rule: the loop, the prompt, or nowhere because the run does not show the problem?

Priority: the one architectural split that, in this run, made the tutor answer the wrong line, repeat a reply, or score a step the child had already shown. Do not propose a new service, queue, or scoring version.

## Prompt: AI tutor loop and scoring

Read `resolve_block_turn`, `forecast_this_turn`, `score_supported_turn`, and the block-type branches in `kc_loop.py`.

Hold these as already shipped. Recommend a change here only when this run shows they failed:

- A clean pass in the middle of a component does not stop for an extra summary check. The last block, a reveal, and a giveaway still can.
- A blank or dotted reply stores "Say that again?" and spends no try.
- A worked-example reveal states the missing step and does not open the solo problem in that same reply.
- Explanation, then topic/goal, opens on the goal.
- Teach-back keeps the explanation and each follow-up separate (`peer_follow_up`, or `peer_follow_up_1` and `peer_follow_up_2`). The explanation id does not satisfy a follow-up.
- Passage order is central idea, citation, interpretation. A required quote counts. Pointing at the span assists the citation only. A reread spends no try.
- Topic/goal scores the authored goal. Multiple choice scores the option frozen for that visit. Case study keeps prediction, rule, and transfer apart. Socratic keeps the thesis and each counterexample apart, and the substep name stays `counterexample_probe`. Spot the flaw keeps identify and repair apart.
- Known, fragile, and unassessed are the verdicts. Stars stay 10 per finished block, 25 per finished topic, plus 5 only when every assessed requirement is independent on the first scored try with no give-up, plus 15 only for a known topic with no reveal.

Ask of this run:

- Which block type still asks again after the child has already said the thing the step required?
- Which close recites the lesson, praises, or asks permission to move on after the loop already decided to finish?
- Which assisted step is marked independent, or the reverse?
- Which non-answer (a question, "tell me more", a reread) spends a try?

Priority: the one loop or score change that fixes the most repeated child-visible miss in this run. Name the requirement key when the miss is a score.

## Prompt: LLM prompt creation

Read `build_kc_prompt` and the seven section builders in `apps/api/app/kc_prompt.py`. Use `harness_prompt_source.py` only to see which constants the harness already knows how to point at. The authoring pages under `apps/web/app/documentation/` must stay true to the code. The strings the web tests require are part of the guide: titles Explanatory, Topic / Goal, Guided Discussion, Assessment & Practice; and the phrases "did not fully complete this block", "Never say congratulations", "Redemption", and "next block opens in its own speech". Each of the seven section headings appears once in "How the prompt is written".

Ask:

- For a bad tutor line in this run, which section actually contained the instruction the model followed?
- Did that section also contain a second instruction that cancelled it (praise and "do not praise", a summary and "do not recap", two questions)?
- Is the active substep the only step described, or does the prompt still show a later block?
- What can be deleted from the prompt because the loop already enforces it?

Priority: one prompt cut or one prompt sentence, tied to a repeated reply shape in this run. Do not add an eighth section. Do not add a new heading inside "How the prompt is written".

## Prompt: child settings and profile

Read `effective_child_profile` in `apps/api/app/models.py` and `normalize_profile`, `normalize_voice_settings`, and `effective_kc_tutor_config` in `apps/api/app/tutor_profile.py`. Then read the "Who you are talking to" and "How to sound" builders in `kc_prompt.py`.

Settings that matter include grade band, reading level, response length, expression style, communication tone, challenge appetite, learning support, interest tags, and the free-text interests. Voice settings include persona, vocabulary, metaphors, humor, and sidekick. Tutor-config blocks include retries, why-confirmation, critique depth, follow-up count, and passage evidence mode (`default_kc_tutor_config`).

Ask:

- Which of those settings changed the words the child heard in this run, and which were stored and then ignored?
- Where a setting is both a profile field and a tutor-config field, which one won?
- Did a younger or less fluent child get the same length and vocabulary as an older fluent child on the same block?
- Did interests show up as a picture inside the explanation, or as a label announced to the child?

Priority: the one setting that this run proves is either ignored or applied so heavily that it fights the lesson. Prefer using a setting that already exists over adding a field.

## Prompt: course structure

Read how a component stores ordered blocks (`stored_blocks`, `substeps_for_block`, KC course create and the component editor). Block fields are the catalog the prompt already describes. Outline, core truth, misconceptions, and the rubric derived from blocks are part of that catalog.

Ask of the courses in this run:

- Is the block order something a child can walk (explain, then show, then try), or does a block ask for an idea the course has not taught?
- Are two blocks testing the same fact?
- Does a passage appear on a component that is not ELA or textual interpretive?
- Is a goal, a quote, a flaw, or a corrected version too vague for the loop's literal check to be fair, so the model is asked to pass a line the code cannot recognize?

Priority: the one authoring change that would have prevented a repeated miss without a code change. If the miss is the code, say that and do not blame the course.

## Prompt: AI child test harness

The end goal is a harness that more accurately mimics different child profiles. Judge the harness by whether a reader can tell the children apart from their lines alone, and whether a tutor bug is still visible when the child plays that profile honestly.

Read:

- `starter_children()` and `blank_traits()` in `apps/api/app/harness_personas.py`
- The child prompt builder used by the harness (search `apps/web` for the child system prompt and `apps/api/app/harness.py` for the persona payload sent to that prompt)
- `apps/web/lib/harness-runner.ts` and the claim / turn / finish routes under `apps/web/app/api/kc/harness/`
- `apps/api/app/harness_checks.py` and `apps/api/app/harness_report.py`

### Child test profiles

Compare every child who spoke in this run with their profile and traits. Traits include curiosity, attention, buttons, boredom, writing, maturity, prior knowledge, tangent, frustration, quit, and what they do when unsure.

Ask:

- Which children produced lines that match the profile (a bored fast mover moves on, an anxious child hesitates, a beginner answers short, a distracted child leaves the lesson)?
- Which children collapsed into one generic "good student" voice?
- Which profile fields never affected a single child line?
- Which trait pairs cannot be true together, or are unused by the child prompt?

Priority: the smallest profile change that makes two children in this run sound different on the same block. Do not add a fifteenth child unless the fourteen cannot cover the miss.

### Child test code

Ask:

- Did the runner store the previous tutor reply against a new child line?
- Did a child turn get written when the tutor call failed or returned blank?
- Did the harness press a button the screen was not showing?
- Did "Got it - move on", "Tell me more", and "No final questions — let's continue!" fire on the substep where that button exists?

Priority: the one runner defect that created a fake tutor failure in this run. If there is none, say so.

### Child prompt

Read the prompt that asks the model to speak as the child. It should take age, profile, and traits, and the last tutor line only.

Ask:

- Does the child prompt tell the model the answer, the rubric, or a later block? If it does, the test is not a child.
- Does it tell the model to follow the profile when that conflicts with being helpful?
- Can the same prompt produce a wrong guess, a side question, a short reply, and a real attempt, or does it always attempt the goal?

Priority: one instruction to add or remove so the next run's child lines are distinguishable by profile and still do not reveal the answer key.

## Closing check

Before you finish, re-read the priority line of each group. Cut any priority that needs a new framework, a new score, or a new prompt section. Keep the one that a child would notice on the next run.
