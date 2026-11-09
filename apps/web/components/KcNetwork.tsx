import type { CSSProperties } from "react";

import type { KcNetwork } from "@/lib/kc";
import { networkStatusClass, type KcUnitStatus } from "@/lib/kc-progress";

export const NETWORK_WIDTH = 840;

export function networkHeight(network: KcNetwork): number {
  const targets = network.nodes.filter((node) => !node.patch);
  const patches = network.nodes.filter((node) => node.patch);
  return Math.max(360, 100 + Math.max(Math.ceil(targets.length / 3), patches.length, 1) * 120);
}

export function NetworkMap({
  network,
  statusByCode,
  noteByCode,
  label = "Component network",
  style,
}: {
  network: KcNetwork;
  statusByCode?: Record<string, KcUnitStatus>;
  noteByCode?: Record<string, string>;
  label?: string;
  style?: CSSProperties;
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
  const height = networkHeight(network);
  return (
    <svg className="kc-net" viewBox={`0 0 ${NETWORK_WIDTH} ${height}`} role="img" aria-label={label} style={style}>
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
            {noteByCode?.[node.code] ? (
              <text x={point.x} y={point.y + 62} textAnchor="middle" className="kc-net-note">
                {noteByCode[node.code]}
              </text>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}
