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
  selectedCode,
  onSelectNode,
  label = "Component network",
  style,
}: {
  network: KcNetwork;
  statusByCode?: Record<string, KcUnitStatus>;
  noteByCode?: Record<string, string>;
  selectedCode?: string | null;
  onSelectNode?: (code: string) => void;
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

  const upstreamCodes = new Set<string>();
  const downstreamCodes = new Set<string>();
  if (selectedCode) {
    for (const edge of network.edges) {
      if (edge.to_code === selectedCode) upstreamCodes.add(edge.from_code);
      if (edge.from_code === selectedCode) downstreamCodes.add(edge.to_code);
    }
  }

  return (
    <svg className="kc-net" viewBox={`0 0 ${NETWORK_WIDTH} ${height}`} role="img" aria-label={label} style={style}>
      {network.edges.map((edge, index) => {
        const from = pos.get(edge.from_code);
        const to = pos.get(edge.to_code);
        if (!from || !to) return null;
        const isUpstream = Boolean(selectedCode && edge.to_code === selectedCode);
        const isDownstream = Boolean(selectedCode && edge.from_code === selectedCode);
        const edgeClasses = [
          edge.kind === "encompasses" ? "is-encompass" : "is-prereq",
          isUpstream ? "is-edge-upstream" : "",
          isDownstream ? "is-edge-downstream" : "",
          selectedCode && !isUpstream && !isDownstream ? "is-edge-dim" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <line
            key={index}
            x1={from.x}
            y1={from.y}
            x2={to.x}
            y2={to.y}
            className={edgeClasses}
          />
        );
      })}
      {network.nodes.map((node) => {
        const point = pos.get(node.code);
        if (!point) return null;
        const isSelected = selectedCode === node.code;
        const isNeighbor = upstreamCodes.has(node.code) || downstreamCodes.has(node.code);
        const mastery = noteByCode?.[node.code];
        const className = [
          node.patch ? "is-patch" : "",
          networkStatusClass(statusByCode?.[node.code], mastery),
          isSelected ? "is-selected" : "",
          isNeighbor ? "is-neighbor" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <g
            key={node.code}
            className={`kc-net-node${onSelectNode ? " is-clickable" : ""}${isSelected ? " is-selected" : ""}`}
            data-code={node.code}
            role={onSelectNode ? "button" : undefined}
            tabIndex={onSelectNode ? 0 : undefined}
            aria-label={onSelectNode ? `Inspect ${node.title}` : undefined}
            aria-pressed={onSelectNode ? isSelected : undefined}
            onClick={onSelectNode ? () => onSelectNode(node.code) : undefined}
            onKeyDown={
              onSelectNode
                ? (event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectNode(node.code);
                    }
                  }
                : undefined
            }
          >
            {isSelected ? (
              <circle
                cx={point.x}
                cy={point.y}
                r={34}
                className="kc-net-focus-ring"
              />
            ) : null}
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
