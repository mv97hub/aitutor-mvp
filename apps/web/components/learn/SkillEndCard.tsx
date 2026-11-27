"use client";

import { normalizeEndCard, type SkillEndCard } from "@/lib/graph2";

export function SkillEndCardView({ endCard }: { endCard: SkillEndCard | null | undefined }) {
  const card = normalizeEndCard(endCard);
  if (!card) return null;

  return (
    <section className="skill-end-card" aria-label="Thinking skills you showed">
      <h3>What you showed</h3>
      <ul className="skill-end-card-list">
        {card.items.map((item) => (
          <li key={item.skill} className="skill-end-card-item">
            <strong className="skill-end-card-label">{item.label}</strong>
            <p className="skill-end-card-sentence">{item.sentence}</p>
            <blockquote className="skill-end-card-quote">&ldquo;{item.quote}&rdquo;</blockquote>
          </li>
        ))}
      </ul>
    </section>
  );
}
