# Three reviewed lesson corrections for Myuran

These unit files address item 3 of the [November 26 test handover](../2026-11-26-ai-tutor-test-handover.md). Each updates one component in an existing course. The course editor stores lessons in the database. Merging this PR adds the files and tutor support for grading source attribution. Applying a unit file to a course is a subsequent editorial decision.

| Course and prepared unit file | What changes for the learner |
| --- | --- |
| Romeo and Juliet · [Scenes with Hidden Meanings](romeo-and-juliet.json) | The two open-ended topics become reading passages. Each gives the act, scene, speakers, short excerpts and an interpretation question. The two choice blocks keep their positions. |
| AP Macroeconomics · [Price Indices and Inflation](price-indices.json) | The introductory notes and explanation distinguish index points from a percentage. A choice question checks the distinction using 108 and 115. The existing basket exercise with an $18 total, CPI of 225 and about 38.5% inflation is preserved. |
| GCSE History · [Weimar Recovery and Its Limits](weimar-recovery.json) | The opening sets the 1923 stabilisation before the 1924–29 recovery. A new choice distinguishes the initial Rentenmark issue from the later Reichsmark. |

## Evidence behind the edits

I compared the completed run with read-only course exports obtained from the app on November 26, 2026. The saved prompts contain the matching balcony/Paris teaching notes, CPI formula and Weimar opening criteria. The exports establish what these versions contain. Neither the run nor the exports provide an immutable per-turn content revision.

- In chat `8e8153d3`, turn 3, a line from the Capulets’ feast earned credit as balcony-scene evidence. The revised balcony passage supplies Juliet’s words about Romeo’s name and identifies Romeo as listening. A directly quoted line from a different scene cannot satisfy this task on its own. A close paraphrase is available when the tutor profile permits it. [Feast, Act 1.5](https://www.folger.edu/explore/shakespeares-works/romeo-and-juliet/read/1/5/) · [Orchard, Act 2.2](https://www.folger.edu/explore/shakespeares-works/romeo-and-juliet/read/2/2/)
- In `df4690ba`, turn 11, the tutor placed Juliet’s words to her mother in the conversation with Paris. In `719c1ae3`, turn 18, it described a marriage that had already taken place as a future plan. The original activities requested evidence without supplying the scene. The corrected passage identifies Juliet, Paris, the Friar’s presence and the existing marriage. It leaves room for a supported interpretation of Juliet’s ambiguous pronoun. The tutor gets an explicit instruction to identify a mismatched source and invite a reread. [Lady Capulet, Act 3.5](https://www.folger.edu/explore/shakespeares-works/romeo-and-juliet/read/3/5/) · [Friar Lawrence’s cell, Act 4.1](https://www.folger.edu/explore/shakespeares-works/romeo-and-juliet/read/4/1/)
- In `9be0be51`, turn 5, neither offered interpretation of the index change was correct. The authored retrieval formula already gives the right denominator. The new item works from one pair of observations in the same series. Subtracting gives 7 index points. Dividing by 108 and multiplying by 100 gives 6.48% to two decimals. The child can select the valid rate, and the tutor can explain either distractor. [BLS method for calculating percent changes](https://www.bls.gov/cpi/factsheets/calculating-percent-changes.htm)
- In `0567ee3b`, turn 8, the tutor dated the Rentenmark to 1924. The later authored explanation already distinguishes the years. The opening criterion included the introduction of the Rentenmark within a goal framed around 1924–29. Its new notes date the first issue to 15 November 1923. The Reichsmark followed in 1924. [Bundesbank on the first issue](https://www.bundesbank.de/resource/blob/607316/a59d865e30ec35e44bf8bbed551dbcb4/472B63F073F071307366337C94F8C870/glanzstuecke-2014-data.pdf) · [Bundesbank on the 1924 currency law](https://www.bundesbank.de/en/statistics/economic-activity-and-prices/purchasing-power-comparisons-of-historical-amounts-of-money-795290)

## Apply an approved correction

1. Use **Manage KC Courses** to export the selected existing course. Keep that file as a backup. The app shares the authored component with ongoing sessions. Use a test copy for rehearsal and apply editorial changes between learner sessions.
2. From the repository root, run the command below with the actual filenames. It checks the affected component against the reviewed export, preserves all its other fields and creates the same unit as the matching file above. If the component has since been edited, compare the newer lesson with the proposed correction before proceeding.
3. On the same course, load the prepared file, preview it, and choose **Merge**. The preview should contain one unit named **Components**, with one component and 4 blocks for literature, 6 for economics or 8 for history. Use the same deployed version of the importer and tutor that supports the optional passage field `evidence_context`.
4. Export the course again and compare the affected component. On a local rehearsal using all three original exports and the actual import endpoints, the courses kept 12, 42 and 47 components respectively. Exactly one component changed in each course.

```sh
python3 apps/api/scripts/prepare_reviewed_lessons.py original-export.json prepared-unit.json
```

## Verify on a test course

- Reread the passage and check the text and speaker labels. At the citation question, a correct quotation assigned to the wrong character should receive a correction. A quotation from the feast should keep the orchard question open. A correctly attributed paraphrase can advance in the close-paraphrase setting. Exact-quotation mode still requires a quote. The reread uses zero attempts. The new attribution judgment applies only to passages whose author supplies source context.
- On the CPI choice, select the index-point answer and check the explanation. Select the percent answer on a fresh attempt. Tests also generate 100→115, 108→108, and 115→108 using the same calculation. The matching rates are 15%, 0%, and about −6.09%.
- On the currency question, select 1924 on one run and 1923 on another. The first selection should invite a correction and the second should advance to give a reason.
- From `apps/api` run `python -m pytest -q tests/test_reviewed_lessons.py tests/test_passage_ela.py tests/test_kc_course_io.py tests/test_block_close_stage4.py` against a seeded disposable test database. The tests inspect prompts, use controlled semantic judgments and exercise the actual choice scorer. They verify the inputs and saved decisions. The reliability of a live model’s interpretation and feedback wording needs a separate evaluation.
