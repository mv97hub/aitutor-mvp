/** The wrapping totals row from Detailed Progress. */
export function ProgressTotals({
  label,
  items,
}: {
  label: string;
  items: { label: string; value: string | number }[];
}) {
  return (
    <dl className="progress-totals" aria-label={label}>
      {items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
