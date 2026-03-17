'use client';

import React, { useRef, useCallback, useState } from 'react';
import dynamic from 'next/dynamic';
import { getStageColor } from '@/lib/utils';
import { GraphData, GraphNode } from '@/types';

// Dynamic import to avoid SSR issues
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
  ssr: false,
});

// Entity type badge colors (used on nodes when entity_type filter is active)
const ENTITY_TYPE_COLORS: Record<string, string> = {
  investor: '#8b5cf6',   // purple
  customer: '#10b981',   // emerald
  vendor:   '#f59e0b',   // amber
  partner:  '#3b82f6',   // blue
  candidate:'#6366f1',   // indigo
  team:     '#64748b',   // slate
  lead:     '#f97316',   // orange
  advisor:  '#06b6d4',   // cyan
  media:    '#ec4899',   // pink
  other:    '#94a3b8',   // light slate
  self:     '#1e293b',   // dark (YOU node)
};

interface RelationshipGraphProps {
  data: GraphData;
  onNodeClick: (node: GraphNode) => void;
  activeEntityFilter?: string | null;  // 'all' | 'investor' | 'customer' | ...
}

export default function RelationshipGraph({
  data,
  onNodeClick,
  activeEntityFilter,
}: RelationshipGraphProps) {
  const graphRef = useRef<any>();
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);

  const handleNodeClick = useCallback(
    (node: any) => {
      onNodeClick(node as GraphNode);
    },
    [onNodeClick]
  );

  const handleNodeHover = useCallback((node: any) => {
    setHoveredNode(node as GraphNode);
  }, []);

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const label = node.name;
      const fontSize = 12 / globalScale;
      ctx.font = `${fontSize}px Sans-Serif`;
      const textWidth = ctx.measureText(label).width;
      const bckgDimensions = [textWidth, fontSize].map((n) => n + fontSize * 0.2);

      // Node size: YOU node is bigger
      const isYou = node.id && !node.email;
      const nodeSize = isYou ? 10 : 5 + Math.min((node.interaction_count || 0) / 10, 4);

      // Choose color: if entity filter active, use entity color; else use stage color
      let fillColor: string;
      if (activeEntityFilter && activeEntityFilter !== 'all') {
        fillColor = ENTITY_TYPE_COLORS[node.entity_type] || ENTITY_TYPE_COLORS.other;
      } else {
        fillColor = ENTITY_TYPE_COLORS[node.entity_type] !== undefined && node.entity_type !== 'other' && node.entity_type !== 'self'
          ? ENTITY_TYPE_COLORS[node.entity_type]
          : getStageColor(node.relationship_stage);
      }

      // Draw glow ring for YOU node
      if (isYou) {
        ctx.shadowColor = '#6366f1';
        ctx.shadowBlur = 15;
      }

      // Draw node circle
      ctx.fillStyle = fillColor;
      ctx.beginPath();
      ctx.arc(node.x, node.y, nodeSize, 0, 2 * Math.PI);
      ctx.fill();

      // Draw hovered border
      if (hoveredNode && hoveredNode.id === node.id) {
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 2 / globalScale;
        ctx.stroke();
      }

      // Reset shadow
      ctx.shadowBlur = 0;

      // Draw label
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
      ctx.fillRect(
        node.x - bckgDimensions[0] / 2,
        node.y + nodeSize + 2,
        bckgDimensions[0],
        bckgDimensions[1]
      );
      ctx.fillStyle = '#000';
      ctx.fillText(label, node.x, node.y + nodeSize + 2 + bckgDimensions[1] / 2);
    },
    [hoveredNode, activeEntityFilter]
  );

  // CC edges render as dashed gray; primary edges render as solid
  const linkColor = useCallback((link: any) => {
    return link.link_type === 'cc_shared' ? '#c7d2fe' : '#e5e7eb';
  }, []);

  const linkWidth = useCallback((link: any) => {
    return link.link_type === 'cc_shared' ? 0.5 : 1;
  }, []);

  const linkLineDash = useCallback((link: any) => {
    return link.link_type === 'cc_shared' ? [4, 4] : [];
  }, []);

  return (
    <div className="w-full h-full">
      <ForceGraph2D
        ref={graphRef}
        graphData={data}
        nodeCanvasObject={nodeCanvasObject}
        nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI);
          ctx.fill();
        }}
        onNodeClick={handleNodeClick}
        onNodeHover={handleNodeHover}
        linkColor={linkColor}
        linkWidth={linkWidth}
        linkLineDash={linkLineDash}
        backgroundColor="#ffffff"
        cooldownTicks={100}
        onEngineStop={() => {
          if (graphRef.current) {
            graphRef.current.zoomToFit(400, 50);
          }
        }}
      />
    </div>
  );
}
