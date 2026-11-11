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
    intro: "The tutor explains each topic, then the summary check closes the walkthrough without a quiz.",
    tracks: [{ name: "explanation", steps: ["explain_topic", "summary_check"] }],
  },
  {
    title: "Topic / Goal",
    intro: "The topic starts as an explanation. The goal question is asked on main only after the learner moves on. summary_check is the only close, whether the goal was met or the attempt limit was reached.",
    tracks: [{ name: "topic_goal", steps: ["explain", "main", "summary_check"] }],
  },
  {
    title: "Guided Discussion",
    intro: "Dialogue finishes its task substeps, then summary_check offers more discussion or a clean close into the next block.",
    tracks: [
      { name: "socratic", steps: ["initial_thesis", "counterexample_probe", "summary_check"] },
      { name: "case_study", steps: ["predict", "contrast_and_rule", "transfer", "summary_check"] },
      { name: "teach_back", steps: ["initial_explanation", "peer_follow_up", "summary_check"] },
      { name: "curiosity", steps: ["hook_and_predict", "summary_check"] },
    ],
  },
  {
    title: "Assessment & Practice",
    intro: "A correct answer or the attempt limit both land on summary_check. The choice widget is hidden there so the learner replies in chat.",
    tracks: [
      { name: "mcq", steps: ["choice", "awaiting_why", "summary_check"] },
      { name: "worked_example", steps: ["faded_step", "solo_solve", "summary_check"] },
      { name: "spot_the_flaw", steps: ["critique", "summary_check"] },
      { name: "retrieval_check", steps: ["recall", "elaborate_why", "summary_check"] },
    ],
  },
];
