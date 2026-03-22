'use client';

import React, { useRef, useCallback, useState, useEffect, useImperativeHandle, forwardRef } from 'react';
import dynamic from 'next/dynamic';
import { useTheme } from 'next-themes';
import { getStageColor } from '@/lib/utils';
import { GraphData, GraphNode } from '@/types';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });

type GraphMode = 'community' | 'stage' | 'ego';

const ENTITY_TYPE_COLORS: Record<string, string> = {
  investor:  '#8b5cf6',
  customer:  '#10b981',
  vendor:    '#f59e0b',
  partner:   '#3b82f6',
  candidate: '#6366f1',
  team:      '#64748b',
  lead:      '#f97316',
  advisor:   '#06b6d4',
  media:     '#ec4899',
  other:     '#94a3b8',
  self:      '#6366f1',
};

const STAGE_COLORS: Record<string, string> = {
  ACTIVE: '#10b981',
  WARM: '#f59e0b',
  NEEDS_ATTENTION: '#f97316',
  DORMANT: '#94a3b8',
  COLD: '#6b7280',
  AT_RISK: '#ef4444',
};

const COMMUNITY_COLORS = [
  '#8b5cf6', '#10b981', '#f59e0b', '#3b82f6',
  '#ef4444', '#06b6d4', '#ec4899', '#f97316',
];

interface RelationshipGraphProps {
  data: GraphData;
  onNodeClick: (node: GraphNode) => void;
  onLinkClick?: (source: GraphNode, target: GraphNode) => void;
  activeEntityFilter?: string | null;
  highlightNodeIds?: Set<string> | null;
  graphMode?: GraphMode;
  egoNodeId?: string | null;
  externalRef?: React.MutableRefObject<any>;
}

export default function RelationshipGraph({
  data,
  onNodeClick,
  onLinkClick,
  activeEntityFilter,
  highlightNodeIds,
  graphMode = 'community',
  egoNodeId = null,
  externalRef,
}: RelationshipGraphProps) {
  const graphRef = useRef<any>();
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  // Sync internal ref to external ref so parent can call zoom/reset
  useEffect(() => {
    if (externalRef && graphRef.current) {
      externalRef.current = graphRef.current;
    }
  });

  const isDark = mounted && resolvedTheme === 'dark';

  const bgColor       = isDark ? '#0d1117' : '#f8fafc';
  const labelBg       = isDark ? 'rgba(13, 17, 23, 0.85)' : 'rgba(248, 250, 252, 0.85)';
  const labelText     = isDark ? '#e2e8f0' : '#1e293b';
  const hoverStroke   = isDark ? '#fff' : '#000';
  const linkPrimary   = isDark ? '#1e3a5f' : '#cbd5e1';
  const linkCC        = isDark ? '#4f46e5' : '#a5b4fc';

  const handleNodeClick = useCallback((node: any) => { onNodeClick(node as GraphNode); }, [onNodeClick]);
  const handleNodeHover = useCallback((node: any) => { setHoveredNode(node as GraphNode); }, []);
  const handleLinkClick = useCallback((link: any) => {
    if (onLinkClick && link.source && link.target) {
      onLinkClick(link.source as GraphNode, link.target as GraphNode);
    }
  }, [onLinkClick]);

  // Filter data for ego mode
  const filteredData = React.useMemo(() => {
    if (graphMode !== 'ego' || !egoNodeId) return data;
    const connectedIds = new Set<string>();
    connectedIds.add(egoNodeId);
    data.links.forEach((link) => {
      const src = typeof link.source === 'object' ? (link.source as any).id : link.source;
      const tgt = typeof link.target === 'object' ? (link.target as any).id : link.target;
      if (src === egoNodeId) connectedIds.add(tgt);
      if (tgt === egoNodeId) connectedIds.add(src);
    });
    return {
      ...data,
      nodes: data.nodes.filter(n => connectedIds.has(n.id)),
      links: data.links.filter(l => {
        const src = typeof l.source === 'object' ? (l.source as any).id : l.source;
        const tgt = typeof l.target === 'object' ? (l.target as any).id : l.target;
        return connectedIds.has(src) && connectedIds.has(tgt);
      }),
    };
  }, [data, graphMode, egoNodeId]);

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const fontSize = 10 / globalScale;
      const isSelf = node.entity_type === 'self';

      // ── Node Size — scaled down for clean look ──
      // 3 tiers: Large (>0.70 → 8px), Medium (0.40-0.70 → 5.5px), Small (<0.40 → 3.5px)
      // Self node slightly larger at 9px
      let baseSize: number;
      if (isSelf) {
        baseSize = 9;
      } else {
        const sizeScore = node.size_score ?? node.composite_score ?? 0.5;
        if (sizeScore > 0.70) {
          baseSize = 8;
        } else if (sizeScore >= 0.40) {
          baseSize = 5.5;
        } else {
          baseSize = 3.5;
        }
      }

      // ── Node Color by mode ──
      let fillColor: string;
      if (isSelf) {
        fillColor = '#6366f1';
      } else if (graphMode === 'stage') {
        fillColor = STAGE_COLORS[node.relationship_stage] || STAGE_COLORS.COLD;
      } else if (graphMode === 'community' && node.community_id != null) {
        fillColor = COMMUNITY_COLORS[node.community_id % COMMUNITY_COLORS.length];
      } else {
        fillColor = ENTITY_TYPE_COLORS[node.entity_type] || ENTITY_TYPE_COLORS.other;
      }

      // Node opacity for highlight filtering
      const nodeOpacity = highlightNodeIds && highlightNodeIds.size > 0
        ? highlightNodeIds.has(node.id) ? 1 : 0.12
        : 1;
      ctx.globalAlpha = nodeOpacity;

      // Subtle glow for self or hover
      if (isSelf) {
        ctx.shadowColor = '#6366f1';
        ctx.shadowBlur = isDark ? 12 : 6;
      } else if (hoveredNode && hoveredNode.id === node.id) {
        ctx.shadowColor = fillColor;
        ctx.shadowBlur = 8;
      }

      // ── Node Shape ──
      const x = node.x;
      const y = node.y;

      if (isSelf) {
        drawStar(ctx, x, y, baseSize, 5);
        ctx.fillStyle = fillColor;
        ctx.fill();
      } else if (node.entity_type === 'organization' || node.entity_type === 'company') {
        drawRoundedSquare(ctx, x, y, baseSize, 2);
        ctx.fillStyle = fillColor;
        ctx.fill();
      } else if (node.entity_type === 'unknown' || node.entity_type === 'other') {
        drawDiamond(ctx, x, y, baseSize);
        ctx.fillStyle = fillColor;
        ctx.fill();
      } else {
        ctx.beginPath();
        ctx.arc(x, y, baseSize, 0, 2 * Math.PI);
        ctx.fillStyle = fillColor;
        ctx.fill();
      }

      // ── Node Ring: Context Confidence ──
      const confidence = node.confidence_score ?? 0.5;
      ctx.strokeStyle = fillColor;
      ctx.lineWidth = 1 / globalScale;

      if (confidence > 0.75) {
        ctx.stroke();
      } else if (confidence >= 0.45) {
        ctx.setLineDash([2 / globalScale, 2 / globalScale]);
        ctx.stroke();
        ctx.setLineDash([]);
      } else {
        ctx.setLineDash([1 / globalScale, 2 / globalScale]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Hover border
      if (hoveredNode && hoveredNode.id === node.id) {
        ctx.strokeStyle = hoverStroke;
        ctx.lineWidth = 1 / globalScale;
        ctx.setLineDash([]);
        ctx.stroke();
      }

      ctx.shadowBlur = 0;

      // ── Label: Medium+Large visible, Small=hover only ──
      const showLabel = isSelf || baseSize >= 5.5 || (hoveredNode && hoveredNode.id === node.id);

      if (showLabel && globalScale >= 0.4) {
        const firstName = (node.name || '').split(' ')[0];
        const label = node.company ? `${firstName} · ${node.company}` : firstName;

        ctx.font = `${fontSize}px system-ui, sans-serif`;
        const textWidth = ctx.measureText(label).width;

        const padX = fontSize * 0.3;
        const padY = fontSize * 0.15;
        const labelX = x - textWidth / 2 - padX;
        const labelY = y + baseSize + fontSize * 0.25;
        const rectW = textWidth + padX * 2;
        const rectH = fontSize + padY * 2;

        ctx.fillStyle = labelBg;
        ctx.fillRect(labelX, labelY, rectW, rectH);

        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = labelText;
        ctx.fillText(label, x, labelY + rectH / 2);
      }

      ctx.globalAlpha = 1;
    },
    [hoveredNode, activeEntityFilter, isDark, labelBg, labelText, hoverStroke, graphMode, highlightNodeIds]
  );

  // ── Edge Color — subtle teal/cyan like reference design ──
  const linkColor = useCallback((link: any) => {
    if (link.link_type === 'cc_shared') return isDark ? '#2dd4bf40' : '#a5b4fc60';

    const trend = link.sentiment_trend;
    const count = link.interaction_count ?? link.strength ?? 0;

    if (!trend && count < 2) return isDark ? '#1e293b50' : '#e2e8f050';

    if (trend === 'IMPROVING') return isDark ? '#34d39980' : '#05966980';
    if (trend === 'DECLINING') return isDark ? '#f8717180' : '#dc262680';

    // Default — subtle teal/slate
    return isDark ? '#2dd4bf30' : '#94a3b860';
  }, [isDark]);

  // ── Edge Thickness — thinner for cleaner look ──
  const linkWidth = useCallback((link: any) => {
    if (link.link_type === 'cc_shared') return 0.3;

    const count = link.interaction_count ?? Math.round((link.strength || 0.3) * 10);

    if (count >= 11) return 1.8;
    if (count >= 4) return 1.0;
    return 0.4;
  }, []);

  // ── Edge Style ──
  const linkLineDash = useCallback((link: any) => {
    if (link.link_type === 'cc_shared') return [3, 3];
    const count = link.interaction_count ?? link.strength ?? 0;
    if (!link.sentiment_trend && count < 2) return [2, 3];
    if (link.is_bidirectional === false) return [4, 2];
    return [];
  }, []);

  if (!mounted) return null;

  return (
    <div className="w-full h-full">
      <ForceGraph2D
        ref={graphRef}
        graphData={filteredData}
        nodeCanvasObject={nodeCanvasObject}
        nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI);
          ctx.fill();
        }}
        onNodeClick={handleNodeClick}
        onNodeHover={handleNodeHover}
        onLinkClick={handleLinkClick}
        linkColor={linkColor}
        linkWidth={linkWidth}
        linkLineDash={linkLineDash}
        backgroundColor={bgColor}
        cooldownTicks={120}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
        onEngineStop={() => {
          if (graphRef.current) graphRef.current.zoomToFit(400, 40);
        }}
      />
    </div>
  );
}

function drawStar(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number, points: number) {
  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const radius = i % 2 === 0 ? r : r * 0.45;
    const angle = (Math.PI / points) * i - Math.PI / 2;
    const x = cx + Math.cos(angle) * radius;
    const y = cy + Math.sin(angle) * radius;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
}

function drawRoundedSquare(ctx: CanvasRenderingContext2D, cx: number, cy: number, half: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(cx - half + r, cy - half);
  ctx.lineTo(cx + half - r, cy - half);
  ctx.arcTo(cx + half, cy - half, cx + half, cy - half + r, r);
  ctx.lineTo(cx + half, cy + half - r);
  ctx.arcTo(cx + half, cy + half, cx + half - r, cy + half, r);
  ctx.lineTo(cx - half + r, cy + half);
  ctx.arcTo(cx - half, cy + half, cx - half, cy + half - r, r);
  ctx.lineTo(cx - half, cy - half + r);
  ctx.arcTo(cx - half, cy - half, cx - half + r, cy - half, r);
  ctx.closePath();
}

function drawDiamond(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(cx, cy - r);
  ctx.lineTo(cx + r, cy);
  ctx.lineTo(cx, cy + r);
  ctx.lineTo(cx - r, cy);
  ctx.closePath();
}
