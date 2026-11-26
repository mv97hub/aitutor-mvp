export type BlockCloseFlowProps = {
  title: string;
  intro: string;
  tracks: { name: string; steps: string[] }[];
};

const CLOSE = [
  {
    label: "Completed",
    text: "Short summary of what this block covered. Ask whether to keep discussing or close and move on.",
  },
  {
    label: "Attempt limit",
    text: "Say the learner hit the attempt limit and did not fully complete this block. Never say congratulations. Give the missed takeaway, then ask whether to keep trying or move on anyway.",
  },
  {
    label: "Redemption",
    text: "A later reply that shows the goal clears the incomplete mark, stays on summary_check, and asks if they are ready to move on.",
  },
  {
    label: "Close",
    text: "A move-on reply is a brief close only. Passed when the block was completed. Revealed when it was still incomplete. The next block opens in its own speech.",
  },
];

export function BlockCloseFlow({ title, intro, tracks }: BlockCloseFlowProps) {
  return (
    <figure className="kc-flow">
      <figcaption>
        <strong>{title}</strong>
        <span>{intro}</span>
      </figcaption>
      {tracks.map((track) => (
        <div className="kc-flow-track" key={track.name}>
          <span className="kc-flow-name">{track.name}</span>
          <ol>
            {track.steps.map((step, index) => (
              <li key={step}>
                {index > 0 ? <span className="kc-flow-arrow" aria-hidden="true" /> : null}
                <span className={step === "summary_check" ? "kc-flow-node is-summary" : "kc-flow-node"}>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      ))}
      <ol className="kc-flow-close">
        {CLOSE.map((item) => (
          <li key={item.label}>
            <strong>{item.label}</strong>
            <span>{item.text}</span>
          </li>
        ))}
      </ol>
    </figure>
  );
}

export const BLOCK_CLOSE_FLOWS: BlockCloseFlowProps[] = [
  {
    title: "Explanatory",
    intro: "The tutor explains each topic. A clean agreement on the last topic finishes the walkthrough. It does not add another ready check.",
    tracks: [{ name: "explanation", steps: ["explain_topic", "summary_check"] }],
  },
  {
    title: "Topic / Goal",
    intro: "The topic starts as an explanation. The goal is asked on main after the learner moves on. A clean pass in the middle of a component does not stop for summary_check. The last block, a reveal, and a giveaway still do.",
    tracks: [{ name: "topic_goal", steps: ["explain", "main"] }],
  },
  {
    title: "Guided Discussion",
    intro: "Thesis and each counterexample stay separate. Prediction, rule, and transfer stay separate. Teach-back keeps the explanation and each follow-up separate: zero ends on the explanation, one uses peer_follow_up, and two use peer_follow_up_1 then peer_follow_up_2. A clean middle pass does not stop for summary_check.",
    tracks: [
      { name: "socratic", steps: ["initial_thesis", "counterexample_probe"] },
      { name: "case_study", steps: ["predict", "contrast_and_rule", "transfer"] },
      { name: "teach_back", steps: ["initial_explanation", "peer_follow_up"] },
      { name: "teach_back, two follow-ups", steps: ["initial_explanation", "peer_follow_up_1", "peer_follow_up_2"] },
      { name: "curiosity", steps: ["hook_and_predict"] },
    ],
  },
  {
    title: "Assessment & Practice",
    intro: "A correct answer in the middle of a component opens the next block. It does not land on summary_check. A reveal still stops for the close. The choice widget is hidden there so the learner replies in chat.",
    tracks: [
      { name: "mcq", steps: ["choice", "awaiting_why"] },
      { name: "worked_example", steps: ["faded_step", "solo_solve"] },
      { name: "spot_the_flaw", steps: ["critique"] },
      { name: "retrieval_check", steps: ["recall", "elaborate_why"] },
    ],
  },
  {
    title: "Close reading",
    intro: "Central idea, citation, and interpretation stay in that order. A required verbatim quote counts. Pointing at the span assists the citation only. A reread spends no attempt. Passage does not end on summary_check.",
    tracks: [{ name: "passage_ela", steps: ["central_idea", "cite_evidence", "craft_or_inference"] }],
  },
];
