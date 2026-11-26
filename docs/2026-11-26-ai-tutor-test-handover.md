# AI Tutor test handover for Myuran · 26 November 2026

Myuran, run `c2bf3bcf-4558-49b6-9328-f6e572103d74` was created at **2:05:57 p.m. US Eastern on 26 November 2026**. It paired **AI_Child1 through AI_Child14** with four knowledge-component (KC) lessons using tutor model `~deepseek/deepseek-flash-latest`. This review covers all **56 synthetic conversations and 1,338 recorded child turns**, including failed deliveries, and the matching code revision `f545497`. The run selected child actions in rule mode and used `gpt-6-luna` to word some of them. [Original handover][handover] · [Tested source][source] · [Runs screen][runs]

## Handback to Myuran · 26 November, after the merges

PRs [#203](https://github.com/mv97hub/aitutor-mvp/pull/203) through [#211](https://github.com/mv97hub/aitutor-mvp/pull/211) are on main. The original 56-conversation run remains the baseline. Its conclusions, examples and test instructions are below.

**Start with a lost reply.** After the server saves an answer, the network can drop before the child sees the response. The worker must recover that same reply. The PostgreSQL rehearsal interrupted both CPI variants at that point, then resumed each through the worker. Each session kept one child message, one committed decision and one harness turn. A separate test covers recovery at the spending cap. These are the checks to repeat after a future change to scoring, delivery or billing. [Retry and test evidence](https://github.com/mv97hub/aitutor-mvp/pull/206) · [Paired worker rehearsal](https://github.com/mv97hub/aitutor-mvp/pull/211)

**Deployment evidence.** The live test-children page contained the new CPI and reading presets. Reading the original 56-chat run succeeded through the updated API, which loads the new pending-turn database column. A newly created synthetic run recorded API revision `65305c2e2d9108e82387c102405936972e290eb1`. Before the course imports, at 22:18 UTC, the production API reported commit `4a05fc2f622acd7605d2c179fe5af3bde4b5e2a5` and the connected database reported `046_harness_pending_turn`. Operators can repeat the same read-only check after any rollout. [Live API and database revision](https://aitutor-mvp.onrender.com/health/revision). [Migration](../apps/api/alembic/versions/046_harness_pending_turn.py) · [Live harness](https://aitutor-mvp-web.onrender.com/kc-test-children)

### The two hosted CPI conversations

Trishan approved two sequential, one-turn chats on the synthetic CPI fixture with AI_Child5, the default tutor and seed 2611. The paired setting resolved both draws to 530923610. Both used scripted learner wording and a live `gpt-4.1-mini` tutor and judge. Each chat and its single-chat run had a 10¢ stop threshold.

| Learner's exact words | What the tutor did next | Saved outcome |
| --- | --- | --- |
| “Is it the change in CPI divided by the old CPI, times 100?” | Confirmed the formula and asked why the learner divided by the old CPI. | One counted attempt. Advanced from recall to the explanation of why. [Chat download](https://aitutor-mvp-web.onrender.com/api/kc/harness/runs/6c0f39b7-1cca-4ae1-a9a2-867ef4fed73c/download) |
| “The change in CPI divided by the old CPI, times 100.” | Replied “That's right!” and asked why the learner divided by the old CPI. | One counted attempt. Advanced to the same step. [Chat download](https://aitutor-mvp-web.onrender.com/api/kc/harness/runs/ac1509cb-1e57-49e6-9d89-f7c2a55d30d0/download) |

Both runs reached the intended question, delivered one reply and stopped at the turn limit. The two tutor-call estimates were $0.0021760 and $0.0020872, or **$0.0042632 combined**. The original run totals rounded both to zero cents and omitted the final judge cost. The automatic checks flagged no false passes or false failures. The judge awarded the tentative exchange 5/5 for correctness and scoring fairness. Its declarative evaluation retained no tutor-dimension grades, so use the saved answer, tutor reply and progression for that comparison. These observations cover one matched pair on one model. The pricing PR records the post-deployment reconciliation of the two original chats, including the judge tokens. [Spending-cap fix and production evidence #214](https://github.com/mv97hub/aitutor-mvp/pull/214)

**Spending limits.** In the hosted runs, the old accounting rounded each individual chat to whole cents before adding them. Several small charges could disappear from a run total. The fix adds exact decimal costs first and includes each new judge result immediately. On a one-cent run limit, $0.00999 stayed open and $0.01000 stopped new work. A two-writer database test produced $0.021 and tripped a two-cent limit. A provider call already in flight can still finish. [Accounting tests and review #214](https://github.com/mv97hub/aitutor-mvp/pull/214)

**Web dependency.** At 22:12 UTC the JavaScript served by the hosted web app identified itself as Next.js 16.4.5. Its previous version was 16.4.3. Updating cleared the seven advisories reported by npm and built all 29 pages. All 230 web tests and TypeScript passed. [Security update #212](https://github.com/mv97hub/aitutor-mvp/pull/212)

### Three live-course corrections

The courses reviewed for import were **Scenes with Hidden Meanings** (4 blocks), **Price Indices and Inflation** (6 blocks), and **Weimar Recovery and Its Limits** (8 blocks). Fresh production exports still matched the prepared corrections. All three live previews showed one component. The exact-copy rehearsal also caught the older importer changing unit grouping, course outcomes and component order despite this preview. The repaired importer passed a full before-and-after export comparison for all three while preserving the existing rubrics and completion flags. [Reviewed packages and operating procedure](course-corrections/README.md) · [Importer repair #213](https://github.com/mv97hub/aitutor-mvp/pull/213)

**Applied and verified in production.** Trishan confirmed all three courses were idle. Codex backed up, imported and republished each course separately. A second read of the live courses verified that the full document matched its expected after-export, only the named component’s blocks changed, and all three courses were ready for learners.

| Course | Live verification (UTC) | What changed | Preserved |
| --- | --- | --- | --- |
| Romeo and Juliet | 22:18:29 | Sourced passages distinguish the balcony scene from the feast and correctly identify the speakers. | All 12 components in order, existing rubric and completion flags. |
| AP Macroeconomics | 22:18:43 | The CPI example distinguishes a 7-point increase from about 6.48% inflation when the index rises from 108 to 115. | All 42 components in order, existing rubric and completion flags. |
| GCSE History | 22:18:54 | The currency question distinguishes the 1923 Rentenmark from the 1924 Reichsmark. | All 47 components in order, existing rubric and completion flags. |

### What the API regression repairs change for a learner

| Case | Expected result and how to verify |
| --- | --- |
| The learner answers during the opening explanation. | Submit a correct, substantive response before pressing Continue. The progress board should show one independent attempt. Start a second session and press Continue without supplying an answer. Opening the question spends zero attempts. |
| The learner repeats a stored misconception. | Give the same wrong triangle-congruence rule twice. The tutor should reveal the block and continue according to the configured policy. The progress board should retain the fragile outcome and show the reveal. The prerequisite remains available for practice. |
| The tutor supplies a choice. | After a wrong response, have the tutor disclose the correct choice. Select that choice and give a fresh, valid reason. Inspect the two outcomes separately. The choice was assisted, the reason was independent, and the unit remains fragile. |
| The child has forgotten or denies a flaw. | On a recall prompt enter “I forget.” On a spot-the-flaw prompt enter “Looks fine to me.” Both answer the current task. The scorer records a miss without giving independent credit. |
| An interrupted session has a block marked finished but no requirement evidence. | Compare a legacy session with a requirement-scored session containing the same old-style result. The older record retains its historical treatment. In the newer one, the tutor board and parent report must agree that the missing evidence cannot support mastery or a first-try bonus. |

Verification of the combined change started from an empty PostgreSQL database, applied the complete migration chain and loaded the repository seed. **All 541 API tests passed.** All 230 web tests, TypeScript and the 29-page production build passed on the patched web source. The live API schema, previously returning HTTP 500, returned HTTP 200 on the repaired release and described the current creator pipeline. The regression suite also checks that a safety intervention consumes zero attempts after an ordinary answer consumed one, the parent-data migration chain and foreign keys exist, switching the Studio model reaches the actual prompt, and usage reports include the cache hit rate. A retired creator route broke the live API schema. The route was a leftover from the switch to the course pipeline and had no callable implementation. The automated test now retrieves the schema and checks the current pipeline is present. [API repair #213](https://github.com/mv97hub/aitutor-mvp/pull/213)

## Implementation update for Myuran · 26 November, after review

The first three PRs restored fragile and unassessed outcomes in reports, linked tutor replies to their calls, and gave a correct tentative answer the same scoring opportunity as a statement. Review of the tentative-answer change also caught a correct paraphrase that shared no words with the answer key. [Outcome export #203](https://github.com/mv97hub/aitutor-mvp/pull/203) · [Call attribution #204](https://github.com/mv97hub/aitutor-mvp/pull/204) · [Tentative answers #205](https://github.com/mv97hub/aitutor-mvp/pull/205)

The PRs below record the implementation, review findings and reproduction steps. The numbered sections below preserve the original conversation evidence.

| Priority | Implementation | What to check |
| --- | --- | --- |
| 1 | [Recover a lost response #206](https://github.com/mv97hub/aitutor-mvp/pull/206) | Lose the final response and resume. The original tutor reply, one learner attempt and one harness turn should survive. At the spending cap, collecting a saved reply uses no model call. Apply the additive database migration before starting updated workers. |
| 2 | [Track what the tutor supplied #207](https://github.com/mv97hub/aitutor-mvp/pull/207) | Reveal option B, with and without its reason. Inspect the two pieces of credit individually. Then give a fresh problem and check for independent credit. |
| 3 | [Correct three lessons #209](https://github.com/mv97hub/aitutor-mvp/pull/209) | Try the wrong-scene quotation, the change from CPI 108 to 115, and the 1923 currency question. The PR contains three prepared unit files and a rehearsal guide. Myuran can decide when to import each correction into a live course. |
| 4 | [Respect reading and length settings #208](https://github.com/mv97hub/aitutor-mvp/pull/208) | Ask for more on the same task with bite-sized and detailed profiles. Check the coaching separately from any reproduced passage. |
| 5 | [Extend automated learner profiles #211](https://github.com/mv97hub/aitutor-mvp/pull/211) | Use a fixed seed with the tentative and declarative CPI presets. Check whether each target was actually reached. The 24 variants span eight families and use the existing child IDs. For the reader comparison, select the same child and passage in both runs. The temporary response-length setting changes while the learner’s request stays identical. |
| 6 | [Clarify the final invitation #210](https://github.com/mv97hub/aitutor-mvp/pull/210) | Compare “Yes please”, a specific question, and Continue. Acceptance should leave room for the learner to ask. Continue should close exactly once. |

**Initial combined rehearsal.** Codex tested the six draft code revisions together on a disposable PostgreSQL database with controlled model replies. The 66 focused API tests and 230 web tests passed, as did TypeScript. The full API suite had 480 passes and the same 18 failing test IDs as `main` at `58f6a3e`. The production build generated all 29 pages. Its first invocation exited on the existing Next.js 16.4.3 security advisory and the repeat succeeded. The dependency still carries the advisory. The local browser check reached a one-chat preview for AI_Child5 with the CPI fixture, seed 2611 and paired draws. No paid evaluation or live course import was run.

**Retry and profile verification after #206 merged.** Codex tested #211 on `main` at `6ade047` using the worker, FastAPI and disposable PostgreSQL. The hesitant and declarative CPI variants used the same seed. Each worker was interrupted after the tutor committed the decision. Resume returned the originally saved response. Each run had one child message, one decision, one recorded harness turn and one matched scenario opportunity. The tutor replies were controlled and no live model was called. [Retry PR](https://github.com/mv97hub/aitutor-mvp/pull/206) · [Profile PR](https://github.com/mv97hub/aitutor-mvp/pull/211)

**Merge verification.** With all six fixes present on the final review branch (`e925477`), 87 focused API tests, all 230 web tests and TypeScript passed. The full API suite passed 501 tests and retained the same 18 failing test IDs reproduced on the original main revision. Review added coverage for an unsent answer at the spending cap, a revealed numeric option with an independent explanation, a short correctly attributed quotation, the two reader settings, and “yes” after different final questions. The grading and retry tests used controlled replies. The three reviewed lesson corrections are ready for a separately scheduled live import.

## Original decisions requested

**Recommended order.** Start with the export and scoring fixes. The current report hides assisted work, and in real exchanges the tutor both withheld credit for a correct answer and awarded credit for an answer it supplied. Correct the verified course errors alongside that work. Then tune age-specific coaching and broaden the simulated journeys.

At the time of the original test review, all six items were proposed for implementation. The PRs above record the fixes and their verification. A future paid model comparison is a separate decision.

| Order | Scope for approval | What Myuran should see before accepting the fix |
| --- | --- | --- |
| 1 | Export every verdict and trace each reply to its actual call. Recover a lost response safely. | A mixed-outcome export reconciles with stored records. A retry produces one learner attempt. |
| 2 | Grade the substance of a tentative answer. Preserve which parts the tutor supplied. | The same correct formula advances in both phrasings. Copying a revealed option earns assisted credit. |
| 3 | Ground source-dependent lessons and calculations in checked material. | Wrong-scene evidence is corrected and CPI feedback distinguishes index points from percent. |
| 4 | Apply the child’s reading and length settings to elaboration. | A six-year-old asking for more gets one short, useful example at a time. |
| 5 | Give simulated learners the visible lesson and legal actions. Expand profile coverage with paired scenarios. | The simulator can reread the full passage, a realistic child cannot see the key, and a fixed scenario can be replayed. |
| 6 | Align the final invitation with the action the tutor can actually take. | A learner who accepts an invitation gets the promised interaction. An explicit move-on still closes once. |

For sign-off, list item numbers under **Approved for implementation**, **Revise** or **Defer**, with any conditions. In particular, **4** changes a deliberate length override, **5** distinguishes scripted regression tests from realistic behavior, and **6** has a wording-only first option. These are product choices.

## Reading the evidence

In the Runs tab, open the completed 26 November run with the ID above and download its Markdown. Search for an eight-character chat ID below and then the numbered `### Turn` heading within that chat. Turn numbers here are the human-readable headings. Some automatic-check arrays use zero-based positions. The reviewed file was **18,775,556 bytes**, SHA-256 `f40207e3c204ca9d2a0e007cd3660e33b7f5e305a2e30a260687f353aa1a5e42`. [Run download][download]

| Lesson component | Chats | Unit completed | Harness stopped as stuck | 40-turn limit | Route error |
| --- | ---: | ---: | ---: | ---: | ---: |
| Price indices | 14 | 10 | 4 | 0 | 0 |
| Romeo and Juliet | 14 | 12 | 1 | 0 | 1 |
| Weimar Germany | 14 | 6 | 8 | 0 | 0 |
| Developmental psychology | 14 | 7 | 5 | 2 | 0 |
| **Total** | **56** | **35** | **18** | **2** | **1** |

Use the per-chat `Ended` field for this table. All 56 chats finished running, but only 35 reached the end of their unit. A stuck run is a lead for investigation. The child policy, lesson length, tutor, or delivery path can each contribute. The dialogue and turn decisions below are usable even where the attached prompt is unreliable. The four components and a single iteration per pairing support regression testing. Real learners would be needed to establish usefulness or learning gains.

## 1. Fix the record of what happened

**Evidence.** The chat footers list **120 passed blocks** and no other outcome. The turn-level loop records **119 passed, 76 fragile and 34 unassessed** closures. *Fragile* can mean the learner needed help or had still to demonstrate a requirement. *Unassessed* includes participation-only teaching. Seven chats show a closure in the turns and `none stored` in their footers. The one-pass discrepancy is in `e88e9e33`. At turns 18–19 a continue action received a service error, then an already-finished response. Both tutor lines were blank, yet both turn records say “advanced, try counted.” The export alone cannot tell us precisely when the server committed.

In `a6c6318b`, turn 1 is about dolphins. Its attached system prompt calls the learner’s turn 5 remark about sea otters “the last answer.” A conservative count found this mismatch on **592 turns across 52 chats**. Count only prompts whose last-answer field exactly matches a later child utterance of at least 25 characters, unique within that chat, after removing the punctuation appended by the prompt template. That rule misses ambiguous and repeated texts. It also explains why we would avoid choosing a prompt line to edit solely from its position in this download.

**What to change.**

- Read the versioned block verdict and export each committed outcome, including fragile and unassessed. Preserve the meanings of legacy records. The harness currently filters for `passed`, `revealed` and `engaged`. Reuse the scorer’s stored-outcome interpretation. An unfamiliar outcome should remain visible as unknown. [Harness outcome filter][outcome] · [Scorer interpretation][classify]
- Correlate the submitted child turn, committed decision, tutor call and usage using persistent identities. A lesson can have an opening call, an answer call, a transition into the next block, or a failed call. Preserve that role and the block before and after a move. The exporter currently treats excess calls as openings at the front, while the producer combines prompts and usage by position. For historical records, show an unknown association when it cannot be proved. [Call collection][calls] · [Export pairing][pair] · [Decision fallback][decision]
- Reuse the existing session receipt and revision for retries. A receipt is the server’s record that a particular submitted answer was accepted. The harness creates a turn ID per transport call. Keep the same ID and payload when recovering that submission, including a worker reclaim. Reconcile against the committed result before recording another attempt. Distinguish a server commit, a delivered tutor message and an unknown delivery. Five blank turns in four chats make this a real distinction. [Transport][transport] · [Runner][runner] · [Receipt][receipt]

**How to test.** Build a small local session with three committed blocks, one of each current verdict. Include a later block opening between two answers, two distinct learner turns both saying “yes,” and a call with missing usage. Drive the actual export producer as well as the Markdown renderer. Assert exact turn-to-call assignments, the opening’s own position, one row per stored verdict, and explicit missing values. Include a legacy record. The existing download test starts with prepared call and outcome lists, so a renderer-only test would miss this defect. [Existing download test][downloadtest]

Exercise two delivery failures with a mocked transport and a disposable local database. In the first, the request fails before commit. In the second, the final answer commits and the response is lost. Replaying the same ID and payload must produce at most one committed answer, attempt, block outcome and harness turn. A conflicting payload under the same ID must still fail. A separate later turn with identical words must get its own record. Confirm that a blank response cannot inherit the previous turn’s decision. Retain the original export as dated evidence. [Existing receipt tests][receipttest]

## 2. Make the reply and score agree about what the learner demonstrated

**Tentative answers.** In `827263e4` turn 22 the learner gave the correct inflation formula, beginning “Is it the new CPI minus the old CPI…?” The tutor confirmed it, asked again and recorded an uncounted stay. Turn 23 advanced on essentially the same formula. At least **4 of 14 price-index chats** showed that sequence: `5711780a` turns 17–18, `5289a43f` turns 26–27, `827263e4` turns 22–23, and `635b5d2e` turns 30–31. In `d01bfe8f` turn 26 the learner correctly suggested identity achievement and asked whether uncertainty could remain in other areas. The tutor agreed and re-asked. The chat ended stuck at turn 33.

**Assisted answers.** In `38d058e6` turn 16 the tutor explicitly identified choice B and explained it. The learner selected B on turn 17, paraphrased the explanation on turn 20 and got a passed close on turn 21. In `719c1ae3` turns 18–19 the tutor explicitly revealed a mistaken plot interpretation and credited the learner’s repetition. Contrast `5de378a6` turns 12–13: the tutor recognized a correct attachment label, challenged only the claim about future relationships, and accepted the corrected inference. That is the feedback to preserve.

**What to change.** Evaluate evidence for the active requirement before treating a question opener as a request for background. A learner can offer an answer and ask a follow-up in the same message. Give credit for the supported part, answer the question, and ask only for what is missing. In the existing prompt builder, generate the immediate instruction from that judgment. The current loop rejects some question openings before checking the answer, and the side-question instruction tells the tutor to ask again. [Question classifier][questions] · [Prompt instruction][sideprompt]

Use the existing requirement-level record to remember a full disclosure when it happens. For an MCQ, track the disclosed option identity even if its explanation is paraphrased. Preserve independent evidence on other requirements. A later correct response to a fresh problem can provide new evidence. A hint that leaves the learner to solve the problem should be distinguishable from explicitly stating the answer. [MCQ disclosure handling][mcqreveal] · [Requirement scoring][score] · [Stored observation][observation]

| Offline test input | Expected reply and stored outcome |
| --- | --- |
| Same correct CPI formula as a statement, as “Is it …?”, and in a short misspelled paraphrase | Credit the same requirement and advance once in each case. The reply mentions the reasoning without asking for the formula again. |
| Formula omits the denominator, or the learner supplies the CPI but uses the wrong previous year | Credit the correct part. Ask only which starting index belongs in the division. |
| “What does CPI mean?” or “Can I have a hint?” | Answer briefly, keep the active question and attempt count, award no independent evidence. |
| Tutor says “the answer is B” in different words, child clicks B, then repeats the reason | The exposed requirement stays assisted through close and parent/harness reporting. Merely displaying all options does not mark them revealed. |
| A learner solves a new numerical example unaided, or corrects only the overclaim in the attachment case | Preserve fresh independent evidence separately. Check the committed verdict, next prompt and learner-facing reply. |

Extend the existing question, prompt-branch, disclosure and block-close tests with these dialogue pairs. An assertion that a prompt contains a phrase alone cannot establish that the server awarded the right credit. [Question tests][qtests] · [Prompt tests][prompttests] · [Giveaway tests][giveawaytests] · [Scoring tests][scoretests]

### Follow-up rehearsal · Choosing an answer and explaining it

In a fresh multiple-choice question, Evie pointed to a bat in the sky while Noah looked in his baseball bag. The operator selected the flying animal first. The tutor pointed out that Noah looked in his baseball bag. The operator then selected the bat used to hit a ball. When asked for the clue, the operator answered “The fact he looks in his bag.”

The original local scorer recorded the corrected choice as independent on attempt two and the explanation as independent on attempt one. Trishan chose **correct, with a hint** for the explanation. The choice and explanation have separate records: check each one when replaying the case.

| Replay the same question with this feedback | Expected credit for a correct choice | Expected credit for a correct explanation |
| --- | --- | --- |
| “Take another look.” The learner identifies the bag. | Independent | Independent |
| The tutor singles out the bag. The learner uses that clue. | Independent | Assisted |
| The tutor singles out the bag. The learner explains another valid clue in the story. | Independent | Independent |
| The tutor gives the correct choice and its full reason. The learner repeats them. | Assisted | Assisted |

The local replays submit turns through the tutor API, control the model’s judgment about correctness, and read the resulting observations from PostgreSQL. Rereading the whole question or asking “Which detail helped you?” leaves the child to find the evidence. Pointing directly to the bag, including in a question, gives a hint. A rejected explanation that repeats words from a hint still needs another try. A second lesson tests the same distinction with webbed footprints.

The scorer compares words from the tutor’s cue, the authored reason, and the learner’s explanation. A one-word answer or a paraphrase with entirely different vocabulary can escape detection. For a future profile test, pair a child who repeats the clue with one who accurately explains it in their own words and inspect both records. [Scoring follow-up and verification #215](https://github.com/mv97hub/aitutor-mvp/pull/215)

## 3. Give each fact-dependent task an authoritative answer

**Evidence.** In `df4690ba` turns 11–12 the tutor treated Juliet’s words about being satisfied when she sees Romeo as part of her exchange with Paris. In the play she is speaking to Lady Capulet. The learner followed the hint and passed. In `8e8153d3` turns 2–3 the task required evidence from the balcony scene but accepted a quotation from Act 1, scene 5. In `719c1ae3` turns 18–19 the tutor said Juliet was arranging a secret marriage to Romeo in the Friar scene. They were already married. These are at least three affected Shakespeare chats out of 14. [Folger, Act 3.5][act35] · [Act 1.5][act15] · [Act 4.1][act41]

In `9be0be51` turn 5 the tutor said the gap between two CPI readings is the inflation rate and asked whether 108 to 115 means seven dollars or seven percent. Neither answer is correct. It is **7 index points** and **100 × (115 − 108) / 108 ≈ 6.48%**. Turn 10 went on to give the correct general method. A learner still had to reconcile the contradiction.

In `0567ee3b` turn 8 the tutor told the learner that Germany introduced the Rentenmark in 1924. Germany’s central bank dates its first issue to 15 November 1923. Give the Weimar lesson a dated reference for this distinction, and include a test that accepts 1923 and corrects 1924 for the Rentenmark’s introduction. [Deutsche Bundesbank, currency history][rentenmark]

**What to change.** Inspect the version of each affected component that supplied its notes, key and criteria before deciding whether the bad claim came from authoring or generation. The transcript establishes what the tutor said. For literature, attach a checked excerpt with speaker, scene and what inference it supports. Show the relevant text to the learner and use it for grading. Reuse the passage matcher for literal quotations and preserve the permitted close-paraphrase route. A matching string alone cannot establish the correct speaker or interpretation. For calculations, store the two inputs, expected units and worked result with the item. Render examples and evaluate numeric answers from that same calculation. [Topic prompt inputs][topic] · [Passage matching][passage]

**How to test.** Take the fixture through authoring/import, prompt assembly and grading. A valid quotation from the wrong scene should earn feedback about its source. A correctly attributed paraphrase should pass when paraphrases are allowed. A quote from the correct scene with reversed speaker or listener should get targeted correction. A request to reread should show the excerpt without consuming an attempt. For CPI, use 100→115, 108→115, an unchanged index and a falling index. Check both units and the actual question shown, including that a correct answer exists among offered choices. Preserve the useful scaffolding in `5289a43f` turns 19–22, where the learner works through an $18 basket, CPI 225 and approximately 38.5% inflation with help. [Passage tests][passagetests] · [Course round-trip tests][coursetests]

## 4. Make “tell me more” useful to an early reader

**Evidence.** AI_Child2 is six, has emerging reading skills and a preference for one or two short sentences. Across this persona’s 100 turns, all five messages beginning “Tell me more” drew **96–159 words**. In `6c85fd37` turns 1, 2, 8 and 10 the replies were 159, 96, 118 and 102 words. In `6451462d` turn 13 the reply was 115 words. The prompt explicitly permits longer replies when a learner requests elaboration. [Configured profile][profiles] · [Elaboration exception][length] · [Current test contract][lengthtest]

**Proposed product decision.** For a bite-sized preference, “more” should mean one more example or one more step, still within the profile’s length and reading level. A detailed-reading profile can receive a fuller explanation. Preserve an authored passage in full when the lesson calls for it, with short coaching beneath. The existing report flags length by character count, so use it as a signal and test the sentence-level promise directly.

**How to test.** Replay the same concept and request twice using an otherwise identical profile with only response length changed. Check that each bite-sized reply has one or two short coaching sentences, adds a new idea or example, and leaves the learner a clear next action. In the detailed setting, allow elaboration appropriate to that profile. Repeat with a quoted passage and count only the tutor’s own coaching. Update the test that currently expects the override. Use fixture replies locally to verify boundaries and include a wording check on the actual generated response in any subsequently approved evaluation. [Length checks][lengthcheck] · [Passage exception tests][passagetests]

## 5. Make automated children better tests of the learner experience

**What this run exposed.** AI_Child11, the echo persona, used the echo action on **38 of 63 turns** and got stuck in **4 of 4** lessons. AI_Child13, designed to answer correctly, and AI_Child14, designed to answer incorrectly, each completed **4 of 4**. Completion therefore tells us that the lesson found an exit. It says little about what either learner could do independently. Of 943 stored child prompts, 75 included the explicit wording “The right idea is”. These are useful controls for testing the tutor. Keep their results visible separately from tests of how teaching changes a subsequent attempt. [Starter personas][profiles] · [Action selection and child prompt][policy]

**Fix the simulator’s inputs first.** In `6b46cc4b` turns 14–17 the tutor reprinted the passage, but the simulated learner’s next prompt cut off mid-paragraph before the final question. It asked to see the passage again and the chat later ended stuck. The child prompt uses the first 800 characters of the tutor message. In `719c1ae3` turns 4–7 the harness also produced unrelated typed messages during a choice sequence. The app already computes when typing is available. Use that same rule in the runner immediately before sending an action, including nudges or fallbacks. [Child prompt][childprompt] · [Visible actions][actions] · [Runner][runner]

For realistic behavior, give the child generator the visible passage, current question in full, available actions and a short recent exchange. Keep the evaluator’s correct option, acceptance criteria and model grading outside that input. A small per-concept record of what the learner has tried and what help they received is enough to start. Update it from the delivered exchange. Today, some internal state is updated from the intended action, even when the generated words do something different. In `decf5052` turn 13, for example, an action labelled `on_topic_question` produced a substantive answer. Preserve both the planned intent and what the learner actually said for inspection. [State update][state]

**Keep comparisons reproducible.** The run builder advances adjacent chat seeds by 997 and the turn picker uses the same 997 increment. Adjacent chat/turn combinations can therefore draw from the same random stream. AI_Child12’s `decf5052` turns 14–20, `4c334b5b` turns 12–18 and `a859e290` turns 11–17 share the same seven-intent sequence. Derive a stable chat seed from a run seed, scenario identity and repetition, then advance or reconstruct its turn state. For a deliberate A/B pair, share the seed explicitly. Log the seed and configuration with the result. A seed reproduces action selection under a fixed policy. Exact model wording requires saved or mocked replies. [Run seeds][seeds] · [Turn seeds][rng]

AI_Child12 made 34 boundary probes drawn from just five distinct phrases. Add a small set of reviewed, synthetic variants to distinguish an ordinary aside from a request that needs redirection. Count the distinct situations exercised as well as the number of turns.

### Proposed profile scenarios

Keep the fourteen stable persona IDs. The following are **variants and paired scripts** using existing traits and settings, so the team can extend coverage without creating a permanent persona for every combination. Change one feature within a pair, keep its lesson and evidence constant, and include both an expected success and an expected failure where relevant.

| Scenario and starting profile | What to vary | Observable pass condition |
| --- | --- | --- |
| Hesitant but knowledgeable · AI_Child5 | Present the same complete formula tentatively and declaratively, then a confident incomplete formula. | Both complete responses earn equal credit. Only the missing denominator prompts coaching. |
| Short expression or spelling variation · AI_Child9 and AI_Child10 | Within each profile, compare a correct short or misspelled answer with a fluent equivalent and a fluent wrong answer. | Correct concept earns equal credit. Polished wording cannot rescue a wrong inference. Preserve `4c733098` turns 11–13, which accepted “Avoidant, but it dont prove he dont care.” |
| Early reader and avid reader · AI_Child2 and AI_Child8 | Hold the concept and request constant. Toggle response length within each persona. Include a deliberately difficult text as a separately labelled stress case. | Short coaching stays short, the full passage remains available, and a detailed explanation is possible for the learner who wants it. |
| Echo, prompted recall and transfer · AI_Child11 | Replay a verbatim echo, a paraphrase after a reveal, then an independently solved novel item. Compare a learner who still struggles after the same hint. | Echoing and assisted recall stay distinguishable from transfer. An explicit full reveal keeps its evidence history. |
| Misconception and correction · AI_Child14 with AI_Child13 as a control | Preserve the always-wrong and always-right scripts. In a realistic variant, tie the wrong belief to CPI, provide a worked correction, and vary whether the next CPI answer improves. Then switch to Shakespeare. | A relevant correction can change the next attempt. A CPI misconception does not force an unrelated literature answer to be wrong. Report controls separately. |
| Quick mover and reluctant learner · AI_Child3 and AI_Child7 | Try a short acknowledgement, an explicit continue, a request for one more question, and repeated “k” followed by a wish to stop. `aa66b261` turns 26–33 illustrate repeated nudging. | An acknowledgement alone earns no assessed knowledge. Honor the available continue/stop action. The simulator can record disengagement without manufacturing mastery. |
| Aside and safe return to task · AI_Child4 and AI_Child12 | Pair a harmless interest or pet remark with a tutor-identity question or a fictional personal-detail scenario. Repeat at a typed question and at a choice-only card. | On-topic teaching resumes without an attempt penalty for a genuine aside. The child generator can send only an available action. Deliberate API-only robustness probes are reported separately. |
| Clarification, partial understanding and genuine guessing · AI_Child1 and AI_Child6 | Same question with a request for a definition, half an answer plus a follow-up, a lucky correct choice with a wrong reason, and a later sound explanation. | The definition is free, the demonstrated part survives a follow-up, and the score reflects the reasoning required by this item. |

**How to test the simulator itself.**

1. Use a fake child model that captures its input. Give it a passage longer than 800 characters with the final question at the end. On the next turn request a reread. Assert both question and passage are available, and search the captured input for a planted evaluator-only key. A visible answer choice is legitimate. A hidden correct-choice marker is a leak.
2. Present a choice-only snapshot to each realistic behavior path and a mock child that tries to type. Assert the runner submits a visible choice or waits. On a typed step, a genuine clarification is allowed. For a wrong-intent fixture whose generated words are correct, verify the evaluator reads the words and the simulator records the mismatch.
3. Replay fixed scenarios with fixed draws and mocked replies. Change suite ordering, interrupt one worker mid-chat and resume it. Unrelated scenarios keep their own draws, the resumed scenario continues from its saved position, and explicitly paired variants share the intended start. Test the seed inputs and state directly since different random streams can legitimately choose the same action.
4. Track **opportunities** by block type, scenario and outcome. Nine block types appeared in the export’s markers. Add bounded fixtures for `curiosity` and `spot_the_flaw`, the two absent types. Separate age-appropriate lessons from deliberate difficulty stress tests. Start with the paired cases above and cover each relevant block at least once before multiplying every persona by every lesson. [Block and score tests][scoretests] · [Web action tests][actiontests] · [Policy tests][policytests] · [Runner tests][runnertests]

## 6. Offer a closing action the tutor can honor

**Evidence.** In `5a20cfd2` turn 33 the tutor offered to *ask* one more question. The learner accepted on turn 34. The tutor gave a closing summary and the unit ended. The existing flow does support answering one last question *from* the learner. In `9be0be51` turn 24 the learner actually asked for a hint and received a relevant answer before close. The issue is the promise about who will ask. [Closing instruction][closing] · [Existing closing tests][closetests]

**Recommended decision and test.** Use child-facing wording such as “Do you have a question for me before we finish?” whenever that is the supported action. Replay the three paths: a specific question gets one useful answer and close, an explicit continue closes exactly once, and uncertainty about the invitation receives clear guidance. Keep the tutor from promising to quiz the learner when that branch will only summarize. If Myuran wants a tutor-led extra practice question, approve it as a distinct interaction with its own answer turn and explicit scoring policy.

## Verification and approval record

Start with recorded examples and local, deterministic tests. Store the smallest fixture that reproduces each decision. For scoring cases, record the learner’s words, what the tutor had already revealed, the expected next move, the actual visible reply and the committed outcome. A canned model response can prove that recording and progression are correct. To establish that a changed prompt reliably *elicits* the right wording, compare the resulting real utterances in a later, separately approved evaluation.

From `apps/web`, this focused command ran at the tested revision: **28 passed, 0 failed**. It exercises existing behavior. Add the replay cases above to these suites when implementing.

```sh
node --experimental-strip-types --experimental-detect-module --test \
  lib/harness-actions.test.ts lib/harness-policy.test.ts \
  lib/harness-runner.test.ts lib/harness-transport.test.ts
```

From `apps/api`, use the repo’s Python environment and a **disposable local test database** with the schema migrated and the seed loaded for database-backed cases. Some integration fixtures clear a seeded learner’s progress. These are proposed implementation checks. They were not run to produce this document. [Local setup][setup]

```sh
python -m pytest -q tests/test_harness_unit.py tests/test_block_close.py
python -m pytest -q tests/test_phase_a_loop_exits.py tests/test_phase_b_this_turn.py \
  tests/test_side_question.py tests/test_giveaway_revealed.py tests/test_block_close_stage4.py
python -m pytest -q tests/test_kc_course_io.py tests/test_passage_ela.py \
  tests/test_phase_c_short_close.py tests/test_learner_questions.py
python -m pytest -q tests/test_kc.py::test_one_further_question_closes_the_summary_and_elaborate_stays
```

For a later model run, agree the model aliases, persona and lesson versions, seeds, repetitions and spend ceiling with Myuran first. Compare the same scenarios before and after. Report wrongly rejected correct answers per independently labelled correct answer, wrongly awarded independent passes per assisted or wrong answer, and delivered replies per submitted turn. Report stuck, capped and error endings separately and show the denominator for each profile and block. Inspect transcripts where a metric changed. A small set of held-out phrasings and fresh problems helps distinguish a general improvement from memorizing a fixture.

**Original review scope.** The 56-chat counts describe the original run. The handback at the top records subsequent verification and live changes.

[handover]: https://github.com/mv97hub/aitutor-mvp/blob/d6d2848105dae95216ddc52e91b4caf9243a5ab5/docs/handover_2611.MD
[source]: https://github.com/mv97hub/aitutor-mvp/tree/f545497d0ac5ae14f97abfa66a21768f9ea24d93
[runs]: https://aitutor-mvp-web.onrender.com/kc-test-children
[download]: https://aitutor-mvp-web.onrender.com/api/kc/harness/runs/c2bf3bcf-4558-49b6-9328-f6e572103d74/download
[outcome]: ../apps/api/app/harness.py#L1379
[classify]: ../apps/api/app/block_score.py#L372
[calls]: ../apps/api/app/harness.py#L1320
[pair]: ../apps/api/app/harness_download.py#L63
[decision]: ../apps/api/app/harness.py#L1274
[transport]: ../apps/web/lib/harness-transport.ts#L88
[runner]: ../apps/web/lib/harness-runner.ts#L208
[receipt]: ../apps/api/app/turn_receipt.py#L25
[downloadtest]: ../apps/api/tests/test_harness_unit.py#L982
[receipttest]: ../apps/api/tests/test_block_close.py#L393
[questions]: ../apps/api/app/kc_loop.py#L1046
[sideprompt]: ../apps/api/app/kc_prompt.py#L1383
[mcqreveal]: ../apps/api/app/kc_loop.py#L2572
[score]: ../apps/api/app/block_score.py#L627
[observation]: ../apps/api/app/block_score.py#L823
[qtests]: ../apps/api/tests/test_phase_a_loop_exits.py#L112
[prompttests]: ../apps/api/tests/test_phase_b_this_turn.py#L68
[giveawaytests]: ../apps/api/tests/test_giveaway_revealed.py#L102
[scoretests]: ../apps/api/tests/test_block_close_stage4.py
[act35]: https://www.folger.edu/explore/shakespeares-works/romeo-and-juliet/read/3/5/
[act15]: https://www.folger.edu/explore/shakespeares-works/romeo-and-juliet/read/1/5/
[act41]: https://www.folger.edu/explore/shakespeares-works/romeo-and-juliet/read/4/1/
[topic]: ../apps/api/app/kc_prompt.py#L2559
[passage]: ../apps/api/app/kc_blocks.py#L115
[passagetests]: ../apps/api/tests/test_passage_ela.py
[coursetests]: ../apps/api/tests/test_kc_course_io.py
[profiles]: ../apps/api/app/harness_personas.py#L60
[length]: ../apps/api/app/kc_prompt.py#L3424
[lengthtest]: ../apps/api/tests/test_phase_c_short_close.py#L38
[lengthcheck]: ../apps/api/app/harness_checks.py#L608
[policy]: ../apps/web/lib/harness-policy.ts#L270
[childprompt]: ../apps/web/lib/harness-policy.ts#L400
[actions]: ../apps/web/lib/harness-actions.ts#L50
[state]: ../apps/web/lib/harness-runner.ts#L303
[seeds]: ../apps/api/app/harness.py#L413
[rng]: ../apps/web/lib/harness-policy.ts#L236
[actiontests]: ../apps/web/lib/harness-actions.test.ts
[policytests]: ../apps/web/lib/harness-policy.test.ts
[runnertests]: ../apps/web/lib/harness-runner.test.ts
[closing]: ../apps/api/app/kc_prompt.py#L1248
[closetests]: ../apps/api/tests/test_kc.py#L4545
[rentenmark]: https://www.bundesbank.de/resource/blob/607868/195d1b540a2053d42fe9f2b735835115/mL/das-papiergeld-im-deutschen-reich-data.pdf
[setup]: ../README.md#setup
