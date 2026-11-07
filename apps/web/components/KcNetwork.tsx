import type { KcNetwork } from "@/lib/kc";
import { networkStatusClass, type KcUnitStatus } from "@/lib/kc-progress";

export function NetworkMap({
  network,
  statusByCode,
  label = "Component network",
}: {
  network: KcNetwork;
  statusByCode?: Record<string, KcUnitStatus>;
  label?: string;
}) {
  const targets = network.nodes.filter((node) => !node.patch);
  const patches = network.nodes.filter((node) => node.patch);
  const pos = new Map<string, { x: number; y: number }>();
  targets.forEach((node, index) => {
    pos.set(node.code, { x: 130 + (index % 3) * 190, y: 78 + Math.floor(index / 3) * 120 });
  });
  patches.forEach((node, index) => {
    pos.set(node.code, { x: 720, y: 78 + index * 120 });
  });
  const height = Math.max(360, 100 + Math.max(Math.ceil(targets.length / 3), patches.length, 1) * 120);
  return (
    <svg className="kc-net" viewBox={`0 0 840 ${height}`} role="img" aria-label={label}>
      {network.edges.map((edge, index) => {
        const from = pos.get(edge.from_code);
        const to = pos.get(edge.to_code);
        if (!from || !to) return null;
        return (
          <line
            key={index}
            x1={from.x}
            y1={from.y}
            x2={to.x}
            y2={to.y}
            className={edge.kind === "encompasses" ? "is-encompass" : "is-prereq"}
          />
        );
      })}
      {network.nodes.map((node) => {
        const point = pos.get(node.code);
        if (!point) return null;
        const className = [node.patch ? "is-patch" : "", networkStatusClass(statusByCode?.[node.code])]
          .filter(Boolean)
          .join(" ");
        return (
          <g key={node.code}>
            <circle cx={point.x} cy={point.y} r={28} className={className || undefined} />
            <text x={point.x} y={point.y + 46} textAnchor="middle">
              {node.title.length > 22 ? `${node.title.slice(0, 20)}…` : node.title}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
