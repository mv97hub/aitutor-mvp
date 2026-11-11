import Link from "next/link";

import { BLOCK_CONFIG_TITLES } from "@/lib/kc-tutor-config";

export const metadata = { title: "KC Creator · Documentation · AI Tutor" };

export default function KcCreatorDocsPage() {
  return (
    <main className="ds-landing">
      <article className="ds-landing-card is-wide">
        <p>
          <Link href="/documentation">Documentation</Link>
        </p>
        <h1>KC Creator</h1>
        <p>
          KC Creator, at <Link href="/kc-creator">/kc-creator</Link>, edits one knowledge component as an ordered list of
          blocks. KC Course Creator, at <Link href="/kc-studio">/kc-studio</Link>, owns the course list and the
          structure. This page is the editor: choose a course and a component, change the blocks by hand, or draft them
          in the chat.
        </p>

        <h2>How it works</h2>
        <p>
          The left pane is a course dropdown. The list under it shows the components of the selected course: targets in
          course order, then patches. A component that already has blocks shows a short block summary, such as 1
          Curiosity · 2 Topics. Choosing another course opens that course&apos;s first component. A patch can be opened
          here. It is still not a target.
        </p>
        <p>
          The middle pane is the manual editor. Description is a short summary. When the component has a recommended
          sequence, that sentence stays in the description and the editor also lists it above the canvas. Outline
          stays beside the blocks. Topic and goal live on a Topic + Goal block. Save this component writes the fields, including the ordered blocks,
          and clears the course ready flag. Mark complete sits next to Save. It can be used only when the saved
          component has no gaps. Mark complete records that flag. Save and Push clear it, and they clear course ready.
        </p>
        <p>
          The block canvas is the ordered lesson. Each card is one block: its place in the sequence, its type, and the
          fields for that type. Up and Down move a card. Duplicate copies it under the original. Collapse hides the
          fields. Delete removes the card. Add block, above the list and between cards, inserts any of the ten types.
          Changing a card&apos;s type starts that type&apos;s empty fields and keeps the card&apos;s place.
        </p>
        <p>
          AI Block Scope sits at the top right, beside Fast Create All. It is a multi-select of the ten block types,
          labeled with how many are on, or All 10 blocks when every type is on. Select All checks every type. Topic +
          MCQ Only leaves Topic / Goal and Multiple choice. Clearing the last checked type leaves Topic / Goal. The
          choice is saved on the course and is sent with the component chat, so the draft stays inside that scope. The
          canvas can still hold any type you add by hand.
        </p>
        <p>
          The right pane is a conversation about this component only. It is stored for the component. It is not a
          kid-tutor message. A model menu sits in the composer. gpt-4.1 is the default. The chosen model is sent with
          each message. It does not change scoring or edges. If the key for the chosen model is missing, the chat shows
          that missing-key error. The reply recommends an ordered blocks sequence inside the AI Block Scope. The middle
          pane keeps the saved component until Push. Push writes the whole draft, including the blocks. Other components
          stay.
        </p>
        <p>
          Fast Create All fills every empty component of the selected course, pushes the draft, and marks the component
          complete. Empty means the component has no blocks, or every block is still a topic and goal copied from the
          course. A filled acceptance criterion or teaching note, a core truth, another block type, or a pushed draft
          means it is no longer empty. The button walks those components in course order and uses the same AI Block
          Scope. The count beside it is how many of them are done. A push that still has a gap stops on that component
          and shows the gap text.
        </p>
        <p>
          Mark whole course ready sits in the top banner, to the left of the Fast Create count, AI Block Scope, and
          Fast Create All. It shows only when a course is open. It calls the same ready check KC Course Creator uses,
          which sets the course ready when every component can be taught. Mark complete on one component is a different
          control. When the course is already ready, the banner says Course ready and does not offer a second mark. If
          the course still has a gap, that reason shows and the course stays not ready.
        </p>

        <h2>Settings you can change</h2>
        <p>Every component has:</p>
        <ul>
          <li>Description. A short summary. Save and Push keep it, including the recommended-blocks sentence.</li>
          <li>Title.</li>
          <li>Outline. The opening of the component can elaborate it. The field catalog says how the first turn uses it.</li>
          <li>Topics. Each row is a topic and its goal. Add and remove rows.</li>
          <li>Blocks, in the order the tutor will walk them. Every field on those blocks is the field catalog.</li>
          <li>Core truth. The overarching takeaway. The field catalog says how it sits beside the blocks.</li>
          <li>Rubric. Derived from the blocks, in block order. Authors do not type it. The field catalog names the line each block contributes.</li>
          <li>Misconceptions. A filled row needs both a wrong move and a component code. The field catalog says how the tutor listens for them.</li>
          <li>Prerequisite of this component, chosen from the other component codes.</li>
          <li>Encompasses, stability bump, chosen from the other component codes.</li>
        </ul>
        <h2 id="field-catalog">Field catalog</h2>
        <p>
          A component keeps an outline, a core truth, and misconceptions. Rubric is derived from the blocks. Each block
          is an id, a type, and a data object. The id is stored with the block. The author chooses the type. The lists
          below are the data fields, and the component fields that stay beside them.
        </p>
        <p>
          Required means the block is not ready while that field is empty. Optional means a blank value still leaves
          the block ready, unless a later sentence says the blank pulls another field in. The tutor&apos;s What to teach
          section receives only the active block, the acceptance check for its current substep, and the component
          misconceptions. Later blocks stay out of the prompt. This turn is the question or the widget for this
          moment. How those sections are assembled is on{" "}
          <Link href="/documentation/kc-prompt-layers">KC prompt layers</Link>.
        </p>

        <h3>Component</h3>
        <ul>
          <li>
            <strong>Outline</strong> (outline). The big-picture framing before Block 1. When Block 1 is a topic or
            goal, the first turn explains the idea and does not ask. Otherwise This turn elaborates the outline, then
            asks Block 1&apos;s question. A later block does not repeat the outline.
          </li>
          <li>
            <strong>Core truth</strong> (core_truth). The overarching takeaway for the component. It stays on the
            component. Block acceptance checks use the block fields below, and the derived rubric is built from those
            fields.
          </li>
          <li>
            <strong>Wrong move</strong> (wrong_move). One side of a misconception row. The mistaken move the tutor
            listens for. What to teach on the active block includes the component misconceptions.
          </li>
          <li>
            <strong>Broken component</strong> (broken_kc). The other side of that row. The component code for what is
            actually broken. A filled row needs both the wrong move and this code.
          </li>
          <li>
            <strong>Rubric</strong>. Derived, in block order, and returned for progress and chat. Authors do not type
            it. The unit close justifies it. A topic / goal block contributes its goal. A multiple choice block
            contributes its target skill when the question is dynamic, and its question stem when the question is
            static. A case study contributes its invariant principle. A Socratic block contributes its target
            synthesis. A worked example contributes its solo expected answer. Spot the flaw contributes its corrected
            version. Teach-back contributes its required concepts. A retrieval check contributes its expected fact. A
            curiosity block contributes no line. An explanation block contributes no line.
          </li>
        </ul>

        <h3>
          {BLOCK_CONFIG_TITLES.topic_goal} (topic_goal)
        </h3>
        <p>One concept, and what the learner has to say in their own words before the block is done. Ready when topic and goal are filled.</p>
        <ul>
          <li>
            <strong>Topic</strong> (topic). Required. The single concept, step, or causal link to introduce on this
            block. The first turn explains what it is and why it matters, and does not ask. The goal question comes
            only after the learner moves on. What to teach includes the topic.
          </li>
          <li>
            <strong>Goal</strong> (goal). Required. What the learner must explain, justify, or demonstrate in their own
            words. That reply is the acceptance check. This block&apos;s rubric line is the goal. When acceptance
            criteria is blank, the check uses the goal. A one or two word fragment still has to be said as a complete
            sentence before the goal counts as met.
          </li>
          <li>
            <strong>Acceptance criteria</strong> (acceptance_criteria). Optional. The evidence the tutor looks for in
            the reply. What to teach uses it as the acceptance check for this block. Blank means the goal is the check.
          </li>
          <li>
            <strong>Teaching notes</strong> (teaching_notes). Optional. An analogy, a boundary condition, or a framing
            note for the introduction. What to teach includes it when the tutor introduces the topic.
          </li>
        </ul>

        <h3>
          {BLOCK_CONFIG_TITLES.mcq} (mcq)
        </h3>
        <p>
          A question the author wrote, or a question the tutor generates when the block opens. The learner picks on a
          choice widget. The app grades the picked index against the correct index. A wrong pick is set aside, and the
          tutor explains that trap. After a correct pick on a retry, the tutor can ask why that option works before the
          block is done. A dynamic item is generated once, as a stem, choices, a correct index, and distractor
          rationales, and retries stay on that same question.
        </p>
        <ul>
          <li>
            <strong>Mode</strong> (mode). Required. Static or dynamic. Static uses the question you stored. Dynamic
            uses the generation fields, and What to return includes the generated item when the block opens.
          </li>
          <li>
            <strong>Question stem</strong> (question_stem). Required when mode is static. The prompt shown above the
            choice cards. This turn shows it. A static block&apos;s rubric line is this stem.
          </li>
          <li>
            <strong>Choices</strong> (choices). Required when mode is static. Two to five options. Ready when at least
            two choices have text and exactly one is correct.
          </li>
          <li>
            <strong>Choice id</strong> (id), on each choice. The stored letter: a, b, c, or d. The card asks for the
            option text and which one choice is correct.
          </li>
          <li>
            <strong>Option text</strong> (text), on each choice. Required. The label on the card. The choice widget
            shows it.
          </li>
          <li>
            <strong>Correct</strong> (is_correct), on each choice. Required. Exactly one choice is true. The acceptance
            check is that the picked index is that choice.
          </li>
          <li>
            <strong>Distractor trap rationale</strong> (distractor_rationale), on each choice. Optional. Why a learner
            might pick this wrong option, and the conceptual trap it represents. On a wrong pick, What to teach uses it
            when the tutor explains the trap.
          </li>
          <li>
            <strong>Misconception code</strong> (misconception_code), on each choice. Optional. A link from this option
            to a component misconception (broken_kc). What to teach can listen for that misconception.
          </li>
          <li>
            <strong>Correct explanation</strong> (correct_explanation). Optional, and only for a static question. The
            takeaway confirmed when the learner selects the right option. What to teach includes it with that pick.
          </li>
          <li>
            <strong>Target skill</strong> (target_skill). Required when mode is dynamic. The concept, calculation, or
            distinction the generated question must assess. What to teach gives it to the generator. A dynamic
            block&apos;s rubric line is this target.
          </li>
          <li>
            <strong>Difficulty</strong> (difficulty). Optional when mode is dynamic. foundation, standard, or stretch.
            The default is standard. It sets the demand of the generated stem.
          </li>
          <li>
            <strong>Number of choices</strong> (num_choices). Optional when mode is dynamic. An integer from 3 to 5.
            The default is 4. It is how many options the generated question has.
          </li>
          <li>
            <strong>Distractor guidance</strong> (distractor_guidance). Required when mode is dynamic. The plausible
            traps or misconceptions the wrong options should target. What to teach gives it to the generator.
          </li>
          <li>
            <strong>Stem constraints</strong> (stem_constraints). Optional when mode is dynamic. Domain or formatting
            rules for the stem, such as a real-world budgeting scenario with whole dollars. What to teach gives them
            to the generator.
          </li>
        </ul>

        <h3>
          {BLOCK_CONFIG_TITLES.case_study} (case_study)
        </h3>
        <p>
          Two cases that share a deep structure and differ on the critical variable. By default This turn shows both
          cases and the prediction, then asks the learner to contrast them and state the principle, then runs the
          transfer when that prompt is filled and the tutor is set to require it. The other presentation asks for the
          contrast and the principle in the same turn, then the transfer. Ready when Case A, Case B, the prediction
          prompt, and the invariant principle are filled. A filled transfer prompt also needs the expected application.
        </p>
        <ul>
          <li>
            <strong>Case A</strong> (case_a). Required. The first scenario. This turn presents it.
          </li>
          <li>
            <strong>Case B</strong> (case_b). Required. The contrasting scenario, different on the critical variable.
            This turn presents it with Case A.
          </li>
          <li>
            <strong>Prediction prompt</strong> (prediction_prompt). Required. The question that asks the learner to
            predict or judge how the two cases behave. This turn asks it. When the prediction is a binary pick, the
            choice widget offers Case A and Case B. Otherwise the learner types.
          </li>
          <li>
            <strong>Invariant principle</strong> (invariant_principle). Required. The underlying rule that explains the
            difference. The contrast turn&apos;s acceptance check is this principle. This block&apos;s rubric line is
            this field.
          </li>
          <li>
            <strong>Transfer prompt</strong> (transfer_prompt). Optional. A novel third scenario where the learner
            applies the principle. When it is filled, This turn asks it on the transfer step.
          </li>
          <li>
            <strong>Transfer expected</strong> (transfer_expected). Optional, and required once a transfer prompt is
            filled. What a valid application has to include. That reply is the acceptance check on the transfer step.
          </li>
        </ul>

        <h3>
          {BLOCK_CONFIG_TITLES.socratic} (socratic)
        </h3>
        <p>
          A dilemma, a first position, then a counterexample, then a synthesis. Ready when the dilemma, the opening
          probe, at least one counterexample, and the target synthesis are filled.
        </p>
        <ul>
          <li>
            <strong>Central dilemma</strong> (central_dilemma). Required. A question, claim, or paradox with a
            non-trivial tension. This turn frames it.
          </li>
          <li>
            <strong>Opening probe</strong> (initial_probe). Required. The question that elicits the learner&apos;s
            first position. This turn asks it. A substantive position advances to the counterexample.
          </li>
          <li>
            <strong>Counterexamples</strong> (counterexamples). Required. One to three edge cases, boundary conditions,
            or counter-scenarios. What to teach uses the relevant one to pressure-test the position and steer it
            toward the target synthesis.
          </li>
          <li>
            <strong>Target synthesis</strong> (target_synthesis). Required. The refined principle the learner must
            articulate after the counterexample. That reply is the acceptance check. This block&apos;s rubric line is
            this field. After the retry limit, the tutor can reveal this synthesis.
          </li>
        </ul>

        <h3>
          {BLOCK_CONFIG_TITLES.curiosity} (curiosity)
        </h3>
        <p>
          A mystery, a guess, then a bridge into the rest of the component. Ready when the hook, the prediction
          question, and the bridge are filled. Once the learner engages, the block is recorded complete. A wild guess
          is not treated as a miss.
        </p>
        <ul>
          <li>
            <strong>Phenomenon hook</strong> (phenomenon_hook). Required. A surprising real-world anomaly,
            counterintuitive observation, or mystery. This turn presents it.
          </li>
          <li>
            <strong>Prediction question</strong> (prediction_question). Required. An open question that asks what the
            learner thinks is going on. This turn asks it. The learner&apos;s guess is the engagement, and the block
            does not grade that guess against a stored answer.
          </li>
          <li>
            <strong>Bridge to unit</strong> (bridge_to_unit). Required. The insight that connects the mystery to the
            rest of the component without spoiling later blocks. After the learner engages, the tutor shares it and
            advances. What to teach includes it.
          </li>
          <li>
            <strong>Wonder branches</strong> (wonder_branches). Optional. One to three follow-up curiosities or
            what-if angles. What to teach can offer them, or answer them when the learner asks.
          </li>
        </ul>

        <h3>
          {BLOCK_CONFIG_TITLES.worked_example} (worked_example)
        </h3>
        <p>
          A worked solution with one step hidden, then a parallel problem. Ready when the problem, at least two steps
          with step text, a faded index that points at a step, the solo problem, and the solo expected answer are
          filled.
        </p>
        <ul>
          <li>
            <strong>Problem statement</strong> (problem_statement). Required. The example problem being solved. This
            turn shows it with the worked steps.
          </li>
          <li>
            <strong>Steps</strong> (steps). Required. Two to six steps, in order. This turn shows them with the faded
            step blanked.
          </li>
          <li>
            <strong>Step text</strong> (step_text), on each step. Required. What is done on that step. The acceptance
            check for the faded step uses this text.
          </li>
          <li>
            <strong>Rationale</strong> (rationale), on each step. Why that step is taken. The acceptance check for the
            faded step uses it with the step text when the learner also has to say why the blank works.
          </li>
          <li>
            <strong>Faded step</strong> (faded_step_index). Optional. The zero-based index of the hidden step. When no
            step is marked, the last step is hidden. The index has to fall inside the step list. This turn blanks that
            step and asks the learner to supply it.
          </li>
          <li>
            <strong>Solo problem</strong> (solo_problem). Required. A parallel problem the learner solves after the
            faded step. This turn presents it on the solo step.
          </li>
          <li>
            <strong>Solo expected answer</strong> (solo_expected_answer). Required. The expected result and the method
            criteria for the solo problem. That solution is the acceptance check. This block&apos;s rubric line is this
            field.
          </li>
        </ul>

        <h3>
          {BLOCK_CONFIG_TITLES.spot_the_flaw} (spot_the_flaw)
        </h3>
        <p>
          A flawed piece of work the learner has to diagnose. Ready when the rookie work, the flaw, the underlying
          misconception, and the corrected version are filled. This turn shows the rookie work and asks for the mistake
          and the fix. Identifying the flaw passes when the tutor only asks for the flaw. Identifying the flaw and
          stating the corrected version both pass when the tutor also asks for the fix.
        </p>
        <ul>
          <li>
            <strong>Rookie work</strong> (rookie_work). Required. A fictional student&apos;s flawed claim, faulty plan,
            or buggy steps. This turn presents it.
          </li>
          <li>
            <strong>Flaw description</strong> (flaw_description). Required. The specific error in the rookie work. The
            acceptance check for spotting the flaw uses this description. What to teach holds it until a reveal.
          </li>
          <li>
            <strong>Underlying misconception</strong> (underlying_misconception). Required. The conceptual trap that
            caused the error. What to teach uses it so the tutor can name why that trap is tempting once the flaw is
            caught.
          </li>
          <li>
            <strong>Corrected version</strong> (corrected_version). Required. The repaired reasoning or calculation.
            When the check includes the fix, this is the acceptance check for the correction. This block&apos;s rubric
            line is this field. A reveal can state the flaw and this correction together.
          </li>
        </ul>

        <h3>
          {BLOCK_CONFIG_TITLES.teach_back} (teach_back)
        </h3>
        <p>
          The learner explains the idea to a confused peer. Ready when the peer prompt, at least one required concept,
          and the follow-up question are filled. If the first explanation already covers every required concept and the
          tutor is set to ask no follow-up, the block completes on that reply. Otherwise This turn asks the peer
          follow-up, or probes the missing concept, until those concepts are in the explanation.
        </p>
        <ul>
          <li>
            <strong>Peer prompt</strong> (peer_persona_prompt). Required. The naive peer&apos;s question or confusion.
            This turn frames the explanation in that voice.
          </li>
          <li>
            <strong>Required concepts</strong> (required_concepts). Required. One to four key ideas the explanation
            must include. The acceptance check is that those ideas show up. This block&apos;s rubric line is this list.
          </li>
          <li>
            <strong>Peer follow-up</strong> (peer_follow_up_question). Required. One follow-up or pushback the peer
            asks when an idea is missing, or to test depth. This turn asks it on the follow-up step.
          </li>
        </ul>

        <h3>
          {BLOCK_CONFIG_TITLES.retrieval_check} (retrieval_check)
        </h3>
        <p>
          A recall question with no choices, then a why question. Ready when the recall prompt, the expected fact, the
          why prompt, and the why rationale are filled. This turn asks the recall first. The why step runs when the
          tutor requires it, or when the recall answer did not already explain why.
        </p>
        <ul>
          <li>
            <strong>Recall prompt</strong> (recall_prompt). Required. The cued-recall question. This turn asks it. The
            learner types. There is no choice widget.
          </li>
          <li>
            <strong>Expected fact</strong> (expected_fact). Required. The core fact, definition, or relationship the
            learner must retrieve. That reply is the acceptance check. This block&apos;s rubric line is this field. A
            miss can get a cued hint before a reveal.
          </li>
          <li>
            <strong>Elaborative why prompt</strong> (elaborative_why_prompt). Required. The follow-up that asks why the
            fact holds, or what would happen if it were reversed. This turn asks it on the why step, after affirming
            the recalled fact.
          </li>
          <li>
            <strong>Expected why rationale</strong> (expected_why_rationale). Required. The causal or conceptual
            explanation for the why question. That reply is the acceptance check on the why step.
          </li>
        </ul>

        <h3>
          {BLOCK_CONFIG_TITLES.explanation} (explanation)
        </h3>
        <p>
          The tutor explains one topic at a time, then asks whether the learner has questions or wants that topic
          elaborated. A question stays on the same topic. The next topic starts only when the learner is ready. After
          the last topic, the tutor summarizes every topic and asks if there are final questions. This block never
          quizzes. Ready when it has one to eight topics and every topic has a title and an explanation. Completing it
          does not mark the component fragile.
        </p>
        <ul>
          <li>
            <strong>Block title</strong> (block_title). Optional. The name of the whole walkthrough.
          </li>
          <li>
            <strong>Topics</strong> (topics). Required. One to eight entries. Each needs a title and a detailed
            explanation. Key points and examples or analogies are optional. Add topic appends an entry. Up and Down
            reorder the entries.
          </li>
          <li>
            <strong>Summary takeaway</strong> (summary_takeaway). Optional. The sentence the summary uses after the
            last topic. When it is empty, the tutor synthesizes the topics.
          </li>
        </ul>

        <h2>What to know when using it</h2>
        <ul>
          <li>Choose a course, then a component. With neither selected, the page says to choose a component.</li>
          <li>
            Fast Create All fills components that have no blocks, and components whose blocks are still the course
            topic and goal. It skips a component that already has another block, a filled note, or a core truth.
          </li>
          <li>AI Block Scope limits what the chat and Fast Create All recommend. It does not delete blocks already on the canvas.</li>
          <li>
            Mark whole course ready is the banner control for the open course. Course ready means it is already marked.
            A gap leaves the course not ready and shows the reason.
          </li>
          <li>The chat draft is not the saved component until Push.</li>
          <li>Push and Save both clear Mark complete and mark the course not ready.</li>
          <li>Mark complete stays unavailable while any gap string would show on the structure row.</li>
          <li>
            How the tutor says a block is set on <Link href="/admin/agent-customizations">Agent customizations</Link>,
            and those settings are listed on <Link href="/documentation/kc-prompt-layers">KC prompt layers</Link>. The
            fields on each block are the field catalog on this page.
          </li>
        </ul>
      </article>
    </main>
  );
}
