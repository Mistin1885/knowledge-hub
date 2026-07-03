import { useEffect, useRef, useState } from 'react';
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force';
import { select } from 'd3-selection';
import { zoom, zoomIdentity, type ZoomTransform } from 'd3-zoom';
import { drag, type D3DragEvent } from 'd3-drag';
import type { GraphData, GraphNode } from '../../api/types';

interface SimNode extends GraphNode, SimulationNodeDatum {}
interface SimLink extends SimulationLinkDatum<SimNode> {
  kind: 'link' | 'tag';
}

function nodeRadius(node: SimNode): number {
  if (node.is_tag) return 6;
  return 4 + Math.min(Math.sqrt(node.link_count || 0) * 2.2, 14);
}

export default function GraphCanvas({
  data,
  onNodeClick,
}: {
  data: GraphData;
  onNodeClick: (node: GraphNode) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const transformRef = useRef<ZoomTransform>(zoomIdentity);
  const clickRef = useRef(onNodeClick);
  clickRef.current = onNodeClick;
  const [tooltip, setTooltip] = useState<{ x: number; y: number; title: string } | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!container || !canvas || !ctx) return;

    const dpr = window.devicePixelRatio || 1;
    let width = container.clientWidth;
    let height = container.clientHeight;

    const nodes: SimNode[] = data.nodes.map((n) => ({ ...n }));
    const nodeIds = new Set(nodes.map((n) => n.id));
    const links: SimLink[] = data.edges
      .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
      .map((e) => ({ source: e.source, target: e.target, kind: e.kind }));

    const draw = () => {
      const t = transformRef.current;
      const dark = document.documentElement.classList.contains('dark');
      ctx.save();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.setTransform(dpr * t.k, 0, 0, dpr * t.k, dpr * t.x, dpr * t.y);

      for (const link of links) {
        const s = link.source as SimNode;
        const g = link.target as SimNode;
        if (s.x === undefined || s.y === undefined || g.x === undefined || g.y === undefined) {
          continue;
        }
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(g.x, g.y);
        ctx.strokeStyle =
          link.kind === 'tag'
            ? 'rgba(245, 158, 11, 0.28)'
            : dark
              ? 'rgba(168, 162, 158, 0.32)'
              : 'rgba(120, 113, 108, 0.28)';
        ctx.lineWidth = 1 / t.k;
        ctx.stroke();
      }

      for (const node of nodes) {
        if (node.x === undefined || node.y === undefined) continue;
        const r = nodeRadius(node);
        if (node.is_tag) {
          ctx.fillStyle = '#f59e0b';
          ctx.fillRect(node.x - r, node.y - r, r * 2, r * 2);
        } else {
          ctx.beginPath();
          ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
          ctx.fillStyle = node.status === 'archived' ? '#a8a29e' : '#6366f1';
          ctx.fill();
        }
      }

      if (t.k >= 1) {
        ctx.font = `${11 / t.k}px ui-sans-serif, system-ui, sans-serif`;
        ctx.fillStyle = dark ? '#c4c0bc' : '#57534e';
        ctx.textAlign = 'center';
        for (const node of nodes) {
          if (node.x === undefined || node.y === undefined) continue;
          const label = node.title.length > 28 ? `${node.title.slice(0, 27)}…` : node.title;
          ctx.fillText(label, node.x, node.y + nodeRadius(node) + 12 / t.k);
        }
      }
      ctx.restore();
    };

    const simulation = forceSimulation(nodes)
      .force(
        'link',
        forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance(70)
          .strength(0.5),
      )
      .force('charge', forceManyBody().strength(-180))
      .force('center', forceCenter(width / 2, height / 2))
      .force('collide', forceCollide<SimNode>().radius((d) => nodeRadius(d) + 4))
      .on('tick', draw);

    const resize = () => {
      width = container.clientWidth;
      height = container.clientHeight;
      canvas.width = Math.max(1, width * dpr);
      canvas.height = Math.max(1, height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      simulation.force('center', forceCenter(width / 2, height / 2));
      draw();
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);

    const findNode = (wx: number, wy: number): SimNode | undefined => {
      let best: SimNode | undefined;
      let bestDist = Infinity;
      for (const node of nodes) {
        if (node.x === undefined || node.y === undefined) continue;
        const r = nodeRadius(node) + 3;
        const dx = wx - node.x;
        const dy = wy - node.y;
        const d2 = dx * dx + dy * dy;
        if (d2 < r * r && d2 < bestDist) {
          best = node;
          bestDist = d2;
        }
      }
      return best;
    };

    const findAtPointer = (offsetX: number, offsetY: number) => {
      const t = transformRef.current;
      return findNode(t.invertX(offsetX), t.invertY(offsetY));
    };

    const selection = select(canvas);

    const dragBehavior = drag<HTMLCanvasElement, unknown, SimNode | undefined>()
      .container(canvas)
      .subject((event) => {
        const se = event.sourceEvent as MouseEvent;
        return findAtPointer(se.offsetX, se.offsetY);
      })
      .on('start', (event: D3DragEvent<HTMLCanvasElement, unknown, SimNode>) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
      })
      .on('drag', (event: D3DragEvent<HTMLCanvasElement, unknown, SimNode>) => {
        const t = transformRef.current;
        const se = event.sourceEvent as MouseEvent;
        event.subject.fx = t.invertX(se.offsetX);
        event.subject.fy = t.invertY(se.offsetY);
      })
      .on('end', (event: D3DragEvent<HTMLCanvasElement, unknown, SimNode>) => {
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
      });

    const zoomBehavior = zoom<HTMLCanvasElement, unknown>()
      .scaleExtent([0.15, 4])
      .filter((event: MouseEvent | WheelEvent) => {
        if (event.type === 'wheel') return true;
        if (event.type === 'mousedown') {
          if ((event as MouseEvent).button !== 0) return false;
          // Let node drags win over canvas panning.
          return !findAtPointer((event as MouseEvent).offsetX, (event as MouseEvent).offsetY);
        }
        return true;
      })
      .on('zoom', (event) => {
        transformRef.current = event.transform;
        draw();
      });

    selection.call(dragBehavior).call(zoomBehavior);

    let hoveredId: string | null = null;
    const onMouseMove = (e: MouseEvent) => {
      const node = findAtPointer(e.offsetX, e.offsetY);
      canvas.style.cursor = node ? 'pointer' : 'default';
      const nextId = node?.id ?? null;
      if (nextId !== hoveredId) {
        hoveredId = nextId;
        setTooltip(node ? { x: e.offsetX, y: e.offsetY, title: node.title } : null);
      } else if (node) {
        setTooltip({ x: e.offsetX, y: e.offsetY, title: node.title });
      }
    };
    const onMouseLeave = () => {
      hoveredId = null;
      setTooltip(null);
    };
    const onClick = (e: MouseEvent) => {
      const node = findAtPointer(e.offsetX, e.offsetY);
      if (node) clickRef.current(node);
    };
    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('mouseleave', onMouseLeave);
    canvas.addEventListener('click', onClick);

    return () => {
      simulation.stop();
      observer.disconnect();
      selection.on('.zoom', null).on('.drag', null);
      canvas.removeEventListener('mousemove', onMouseMove);
      canvas.removeEventListener('mouseleave', onMouseLeave);
      canvas.removeEventListener('click', onClick);
      setTooltip(null);
    };
  }, [data]);

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      <canvas ref={canvasRef} className="block" />
      {tooltip && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border border-neutral-200 bg-surface px-2 py-1 text-xs text-neutral-800 shadow-lg"
          style={{
            left: Math.min(tooltip.x + 12, (containerRef.current?.clientWidth ?? 300) - 160),
            top: tooltip.y + 12,
          }}
        >
          {tooltip.title}
        </div>
      )}
    </div>
  );
}
