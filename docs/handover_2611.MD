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

Fully analyze the downloaded 56-chat transcript and the GitHub repo together. Read the whole transcript, not a sample, and read the code the transcript depends on. How you analyze it, and how you present what you find, is up to you.

Give overarching suggestions and recommendations. Include the architecture, the design, and the code of the AI Tutor. Make the recommendations concrete and detailed. An overarching principle is to keep the code as simple as feasible while still being an optimal, best-in-class tutor for the child.

Cover every part of the product, including the AI tutor, the LLM prompt creation, the child settings and profile, and the course structure. Group the recommendations by area. Include a priority recommendation in each group.

Also recommend changes to the AI child test harness, including the child test profiles, the child test code, and the child prompt. The end goal is a harness that more accurately mimics different child profiles.
