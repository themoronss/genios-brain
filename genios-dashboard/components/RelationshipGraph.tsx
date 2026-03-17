'use client';

import React, { useRef, useCallback, useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { useTheme } from 'next-themes';
import { getStageColor } from '@/lib/utils';
import { GraphData, GraphNode } from '@/types';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });

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

interface RelationshipGraphProps {
  data: GraphData;
  onNodeClick: (node: GraphNode) => void;
  activeEntityFilter?: string | null;
}

export default function RelationshipGraph({ data, onNodeClick, activeEntityFilter }: RelationshipGraphProps) {
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

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const label = node.name;
      // Keep label visually ~12px regardless of zoom — never go larger than 12
      const fontSize = 12 / globalScale;

      const isSelf = node.entity_type === 'self';
      const baseSize = isSelf ? 10 : 5 + Math.min((node.interaction_count || 0) / 8, 4);
      const nodeSize = baseSize;

      // Color
      let fillColor: string;
      if (isSelf) {
        fillColor = '#6366f1';
      } else if (activeEntityFilter && activeEntityFilter !== 'all') {
        fillColor = ENTITY_TYPE_COLORS[node.entity_type] || ENTITY_TYPE_COLORS.other;
      } else {
        fillColor = (ENTITY_TYPE_COLORS[node.entity_type] && node.entity_type !== 'other' && node.entity_type !== 'self')
          ? ENTITY_TYPE_COLORS[node.entity_type]
          : getStageColor(node.relationship_stage);
      }

      // Glow
      if (isSelf) {
        ctx.shadowColor = '#6366f1';
        ctx.shadowBlur = isDark ? 18 : 8;
      } else if (hoveredNode && hoveredNode.id === node.id) {
        ctx.shadowColor = fillColor;
        ctx.shadowBlur = 10;
      }

      // Circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, nodeSize, 0, 2 * Math.PI);
      ctx.fillStyle = fillColor;
      ctx.fill();

      // Hovered border
      if (hoveredNode && hoveredNode.id === node.id) {
        ctx.strokeStyle = hoverStroke;
        ctx.lineWidth = 1.5 / globalScale;
        ctx.stroke();
      }

      ctx.shadowBlur = 0;

      // Label — only render when zoomed enough to be readable
      if (globalScale >= 0.5) {
        ctx.font = `${fontSize}px system-ui, sans-serif`;
        const textWidth = ctx.measureText(label).width;

        // Label background rect below the node
        const padX = fontSize * 0.4;
        const padY = fontSize * 0.2;
        const labelX = node.x - textWidth / 2 - padX;
        const labelY = node.y + nodeSize + fontSize * 0.3;
        const rectW = textWidth + padX * 2;
        const rectH = fontSize + padY * 2;

        ctx.fillStyle = labelBg;
        ctx.fillRect(labelX, labelY, rectW, rectH);

        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = labelText;
        ctx.fillText(label, node.x, labelY + rectH / 2);
      }
    },
    [hoveredNode, activeEntityFilter, isDark, labelBg, labelText, hoverStroke]
  );

  const linkColor = useCallback((link: any) => {
    return link.link_type === 'cc_shared' ? linkCC : linkPrimary;
  }, [linkPrimary, linkCC]);

  const linkWidth = useCallback((link: any) => {
    return link.link_type === 'cc_shared' ? 0.8 : 1.2;
  }, []);

  const linkLineDash = useCallback((link: any) => {
    return link.link_type === 'cc_shared' ? [4, 4] : [];
  }, []);

  if (!mounted) return null;

  return (
    <div className="w-full h-full">
      <ForceGraph2D
        ref={graphRef}
        graphData={data}
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
