'use client';

import React, { useRef, useCallback, useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { useTheme } from 'next-themes';
import { getStageColor } from '@/lib/utils';
import { GraphData, GraphNode } from '@/types';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });

// Graph view modes per V1 Detailing spec
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

// Stage colors for stage view mode
const STAGE_COLORS: Record<string, string> = {
  ACTIVE: '#10b981',
  WARM: '#f59e0b',
  NEEDS_ATTENTION: '#f97316',
  DORMANT: '#94a3b8',
  COLD: '#6b7280',
  AT_RISK: '#ef4444',
};

// Community detection colors
const COMMUNITY_COLORS = [
  '#8b5cf6', '#10b981', '#f59e0b', '#3b82f6',
  '#ef4444', '#06b6d4', '#ec4899', '#f97316',
];

interface RelationshipGraphProps {
  data: GraphData;
  onNodeClick: (node: GraphNode) => void;
  activeEntityFilter?: string | null;
  graphMode?: GraphMode;
  egoNodeId?: string | null;
}

export default function RelationshipGraph({
  data,
  onNodeClick,
  activeEntityFilter,
  graphMode = 'community',
  egoNodeId = null,
}: RelationshipGraphProps) {
  const graphRef = useRef<any>();
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  const isDark = mounted && resolvedTheme === 'dark';

  // Theme-aware colors
  const bgColor       = isDark ? '#0d1117' : '#f8fafc';
  const labelBg       = isDark ? 'rgba(13, 17, 23, 0.85)' : 'rgba(248, 250, 252, 0.85)';
  const labelText     = isDark ? '#e2e8f0' : '#1e293b';
  const hoverStroke   = isDark ? '#fff' : '#000';
  const linkPrimary   = isDark ? '#334155' : '#cbd5e1';
  const linkCC        = isDark ? '#4f46e5' : '#a5b4fc';

  const handleNodeClick = useCallback((node: any) => { onNodeClick(node as GraphNode); }, [onNodeClick]);
  const handleNodeHover = useCallback((node: any) => { setHoveredNode(node as GraphNode); }, []);

  // Filter data for ego mode
  const filteredData = React.useMemo(() => {
    if (graphMode !== 'ego' || !egoNodeId) return data;

    // Find all nodes connected to ego node
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
      const fontSize = 12 / globalScale;
      const isSelf = node.entity_type === 'self';

      // ── Node Size: 3 tiers from size_score ──
      const sizeScore = node.size_score ?? 0.5;
      let baseSize: number;
      if (isSelf) {
        baseSize = 12;
      } else if (sizeScore > 0.70) {
        baseSize = 9; // Large
      } else if (sizeScore >= 0.40) {
        baseSize = 6; // Medium
      } else {
        baseSize = 4; // Small
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

      // Glow for self or hover
      if (isSelf) {
        ctx.shadowColor = '#6366f1';
        ctx.shadowBlur = isDark ? 18 : 8;
      } else if (hoveredNode && hoveredNode.id === node.id) {
        ctx.shadowColor = fillColor;
        ctx.shadowBlur = 10;
      }

      // ── Node Shape per spec ──
      const x = node.x;
      const y = node.y;

      if (isSelf) {
        // Star shape for user
        drawStar(ctx, x, y, baseSize, 5);
        ctx.fillStyle = fillColor;
        ctx.fill();
      } else if (node.entity_type === 'organization' || node.entity_type === 'company') {
        // Rounded square for organizations
        const half = baseSize;
        const r = 2;
        ctx.beginPath();
        ctx.moveTo(x - half + r, y - half);
        ctx.lineTo(x + half - r, y - half);
        ctx.arcTo(x + half, y - half, x + half, y - half + r, r);
        ctx.lineTo(x + half, y + half - r);
        ctx.arcTo(x + half, y + half, x + half - r, y + half, r);
        ctx.lineTo(x - half + r, y + half);
        ctx.arcTo(x - half, y + half, x - half, y + half - r, r);
        ctx.lineTo(x - half, y - half + r);
        ctx.arcTo(x - half, y - half, x - half + r, y - half, r);
        ctx.closePath();
        ctx.fillStyle = fillColor;
        ctx.fill();
      } else {
        // Circle for people (default)
        ctx.beginPath();
        ctx.arc(x, y, baseSize, 0, 2 * Math.PI);
        ctx.fillStyle = fillColor;
        ctx.fill();
      }

      // ── Node Border: Confidence indicator ──
      const confidence = node.confidence_score ?? 0.5;
      ctx.strokeStyle = fillColor;
      ctx.lineWidth = 1.5 / globalScale;

      if (confidence > 0.75) {
        // Solid border — high confidence
        ctx.stroke();
      } else if (confidence >= 0.45) {
        // Dashed border — medium confidence
        ctx.setLineDash([3 / globalScale, 3 / globalScale]);
        ctx.stroke();
        ctx.setLineDash([]);
      } else {
        // Dotted border — low confidence
        ctx.setLineDash([1 / globalScale, 3 / globalScale]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Hover border
      if (hoveredNode && hoveredNode.id === node.id) {
        ctx.strokeStyle = hoverStroke;
        ctx.lineWidth = 1.5 / globalScale;
        ctx.setLineDash([]);
        ctx.stroke();
      }

      ctx.shadowBlur = 0;

      // ── Label: "First Name · Company" for medium/large only ──
      const showLabel = isSelf || sizeScore >= 0.40 || (hoveredNode && hoveredNode.id === node.id);

      if (showLabel && globalScale >= 0.4) {
        const firstName = (node.name || '').split(' ')[0];
        const label = node.company ? `${firstName} · ${node.company}` : firstName;

        ctx.font = `${fontSize}px system-ui, sans-serif`;
        const textWidth = ctx.measureText(label).width;

        const padX = fontSize * 0.4;
        const padY = fontSize * 0.2;
        const labelX = x - textWidth / 2 - padX;
        const labelY = y + baseSize + fontSize * 0.3;
        const rectW = textWidth + padX * 2;
        const rectH = fontSize + padY * 2;

        ctx.fillStyle = labelBg;
        ctx.fillRect(labelX, labelY, rectW, rectH);

        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = labelText;
        ctx.fillText(label, x, labelY + rectH / 2);
      }
    },
    [hoveredNode, activeEntityFilter, isDark, labelBg, labelText, hoverStroke, graphMode]
  );

  // ── Edge encoding ──
  const linkColor = useCallback((link: any) => {
    if (link.link_type === 'cc_shared') return linkCC;

    // Color by sentiment trend
    const trend = link.sentiment_trend;
    if (trend === 'IMPROVING') return '#10b981'; // Green
    if (trend === 'DECLINING') return '#ef4444'; // Red

    return linkPrimary; // Grey/neutral
  }, [linkPrimary, linkCC]);

  const linkWidth = useCallback((link: any) => {
    if (link.link_type === 'cc_shared') return 0.6;

    // Thickness by interaction strength
    const strength = link.strength || 0.3;
    if (strength > 0.7) return 2.0;  // Thick (11+ interactions)
    if (strength > 0.3) return 1.2;  // Medium (4-10)
    return 0.6;                       // Thin (1-3)
  }, []);

  const linkLineDash = useCallback((link: any) => {
    if (link.link_type === 'cc_shared') return [4, 4];
    // Dashed for one-sided relationships
    if (link.is_bidirectional === false) return [6, 3];
    return []; // Solid for bidirectional
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
          ctx.arc(node.x, node.y, 10, 0, 2 * Math.PI);
          ctx.fill();
        }}
        onNodeClick={handleNodeClick}
        onNodeHover={handleNodeHover}
        linkColor={linkColor}
        linkWidth={linkWidth}
        linkLineDash={linkLineDash}
        backgroundColor={bgColor}
        cooldownTicks={120}
        onEngineStop={() => {
          if (graphRef.current) graphRef.current.zoomToFit(400, 60);
        }}
      />
    </div>
  );
}

// Helper: draw a star shape
function drawStar(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number, points: number) {
  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const radius = i % 2 === 0 ? r : r * 0.5;
    const angle = (Math.PI / points) * i - Math.PI / 2;
    const x = cx + Math.cos(angle) * radius;
    const y = cy + Math.sin(angle) * radius;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
}
