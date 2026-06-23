import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import ForceGraph2D from 'react-force-graph-2d'

import LayoutsControl from '@/components/graph/LayoutsControl'
import GraphControl from '@/components/graph/GraphControl'
import ZoomControl from '@/components/graph/ZoomControl'
import FullScreenControl from '@/components/graph/FullScreenControl'
import Settings from '@/components/graph/Settings'
import GraphSearch, { SearchOptionItem } from '@/components/graph/GraphSearch'
import GraphLabels from '@/components/graph/GraphLabels'
import PropertiesView from '@/components/graph/PropertiesView'
import SettingsDisplay from '@/components/graph/SettingsDisplay'
import Legend from '@/components/graph/Legend'
import LegendButton from '@/components/graph/LegendButton'

import { useSettingsStore } from '@/stores/settings'
import { useGraphStore } from '@/stores/graph'
import useLightragGraph from '@/hooks/useLightragGraph'

// ── FGMethods: imperative API we use from react-force-graph-2d ──────────────
// ForceGraphMethods doesn't expose d3 simulation helpers in its types,
// so we define our own interface and use `as any` on the ref.
export interface FGMethods {
  d3Force: (name: string, force?: any) => any
  d3AlphaMin: (alpha?: number) => any
  d3VelocityDecay: (decay?: number) => any
  d3ReheatSimulation: () => void
  zoomToFit: (duration?: number, padding?: number) => void
  zoom: (k?: number, duration?: number) => any
  centerAt: (x?: number, y?: number, duration?: number) => void
  refresh?: () => void
  pauseAnimation: () => void
  resumeAnimation: () => void
}

// ── Color helpers ─────────────────────────────────────────────────────────────
const hexToRgba = (hex: string, alpha: number): string => {
  const h = hex.replace('#', '')
  const r = parseInt(h.substring(0, 2), 16)
  const g = parseInt(h.substring(2, 4), 16)
  const b = parseInt(h.substring(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

// Build a neighbour set for a given node id
const buildNeighbourSet = (
  nodeId: string,
  links: any[]
): Set<string> => {
  const neighbours = new Set<string>()
  neighbours.add(nodeId)
  for (const link of links) {
    const src = typeof link.source === 'object' ? link.source.id : link.source
    const tgt = typeof link.target === 'object' ? link.target.id : link.target
    if (src === nodeId) neighbours.add(tgt)
    if (tgt === nodeId) neighbours.add(src)
  }
  return neighbours
}

// ─────────────────────────────────────────────────────────────────────────────

const GraphViewer = () => {
  const fgRef = useRef<FGMethods | undefined>(undefined)
  const containerRef = useRef<HTMLDivElement>(null)

  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })
  // ── Repaint ticker: incrementing this forces ForceGraph2D to re-render ────
  const [repaintTick, setRepaintTick] = useState(0)

  // ── Data hook ────────────────────────────────────────────────────────────
  useLightragGraph()

  const rawGraph = useGraphStore.use.rawGraph()
  const selectedNode = useGraphStore.use.selectedNode()
  const isFetching = useGraphStore.use.isFetching()
  const moveToSelectedNode = useGraphStore.use.moveToSelectedNode()

  const showPropertyPanel = useSettingsStore.use.showPropertyPanel()
  const showNodeSearchBar = useSettingsStore.use.showNodeSearchBar()
  const showLegend = useSettingsStore.use.showLegend()

  // ── Responsive container ────────────────────────────────────────────────
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new ResizeObserver(entries => {
      const rect = entries[0].contentRect
      setDimensions({ width: rect.width, height: rect.height })
    })
    observer.observe(el)
    setDimensions({ width: el.clientWidth, height: el.clientHeight })
    return () => observer.disconnect()
  }, [])

  // ── Convert rawGraph → ForceGraph2D format ──────────────────────────────
  const graphData = useMemo(() => {
    if (!rawGraph || !rawGraph.nodes.length) {
      return { nodes: [] as any[], links: [] as any[] }
    }

    // Degree range for size scaling
    const degrees = rawGraph.nodes.map(n => n.degree ?? 0)
    const maxDegree = Math.max(...degrees, 1)
    const minDegree = Math.min(...degrees, 0)
    const degreeRange = maxDegree - minDegree || 1

    return {
      nodes: rawGraph.nodes.map(n => {
        // Node radius: degree drives size (min 4, max 22)
        const normDeg = ((n.degree ?? 0) - minDegree) / degreeRange
        const radius = 4 + normDeg * 18
        return {
          id: n.id,
          label: n.labels.join(', '),
          color: n.color,
          size: radius,          // visual radius used by canvas painter
          degree: n.degree,
          properties: n.properties
        }
      }),
      links: rawGraph.edges.map(e => ({
        id: e.id,
        source: e.source,
        target: e.target,
        dynamicId: e.dynamicId,
        label: e.properties?.keywords || '',
        weight: typeof e.properties?.weight === 'number' ? e.properties.weight : 1,
        properties: e.properties
      }))
    }
  }, [rawGraph])

  // ── Neighbour set of the selected node ────────────────────────────────────
  const neighbourSet = useMemo(() => {
    if (!selectedNode) return null
    return buildNeighbourSet(selectedNode, graphData.links)
  }, [selectedNode, graphData.links])

  // ── Force canvas redraw when selection/neighbour set changes ──────────────
  // The most reliable way: increment a counter that's passed as a key prop
  // to trigger a full re-render of the canvas.
  useEffect(() => {
    setRepaintTick(t => t + 1)
  }, [neighbourSet, selectedNode])
  useEffect(() => {
    if (!moveToSelectedNode || !selectedNode || !fgRef.current) return
    const nodeData = graphData.nodes.find((n: any) => n.id === selectedNode)
    if (!nodeData || nodeData.x === undefined) return

    fgRef.current.centerAt(nodeData.x, nodeData.y, 600)
    fgRef.current.zoom(3, 600)
    useGraphStore.getState().setMoveToSelectedNode(false)
  }, [moveToSelectedNode, selectedNode, graphData.nodes])

  // ── Canvas node painter ───────────────────────────────────────────────────
  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const { selectedNode: sel, focusedNode: foc } = useGraphStore.getState()

      const isSelected = node.id === sel
      const isFocused = node.id === foc
      const isNeighbour = neighbourSet ? neighbourSet.has(node.id) : true
      const isDimmed = neighbourSet ? !isNeighbour : false

      const x: number = node.x ?? 0
      const y: number = node.y ?? 0
      const r: number = node.size ?? 6
      const rawColor: string = node.color || '#00e0ff'

      // ── Outer glow ring (selected / focused) ─────────────────────────
      if (isSelected || isFocused) {
        const glowR = r * (isSelected ? 2.2 : 1.7)
        const grad = ctx.createRadialGradient(x, y, r * 0.5, x, y, glowR)
        const glowColor = isSelected ? '#ff8a3d' : '#00e0ff'
        grad.addColorStop(0, hexToRgba(glowColor, isSelected ? 0.55 : 0.35))
        grad.addColorStop(1, hexToRgba(glowColor, 0))
        ctx.beginPath()
        ctx.arc(x, y, glowR, 0, Math.PI * 2)
        ctx.fillStyle = grad
        ctx.fill()
      }

      // ── Main circle ──────────────────────────────────────────────────
      ctx.beginPath()
      ctx.arc(x, y, r, 0, Math.PI * 2)

      if (isDimmed) {
        ctx.fillStyle = 'rgba(30,40,60,0.35)'
        ctx.strokeStyle = 'rgba(80,100,130,0.25)'
      } else {
        ctx.fillStyle = hexToRgba(rawColor, isSelected ? 1 : isFocused ? 0.95 : 0.82)
        ctx.strokeStyle = isSelected
          ? '#ff8a3d'
          : isFocused
          ? '#ffffff'
          : hexToRgba(rawColor, 0.55)
      }
      ctx.lineWidth = isSelected ? 2.5 / globalScale : 1.5 / globalScale
      ctx.fill()
      ctx.stroke()

      // ── Label ────────────────────────────────────────────────────────
      if (!isDimmed) {
        const label: string = node.label || node.id
        const fontSize = Math.max(3, Math.min(14 / globalScale, r * 0.9))
        ctx.font = `${fontSize}px 'Inter', sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'

        // label background pill
        const textWidth = ctx.measureText(label).width
        const padX = fontSize * 0.4
        const padY = fontSize * 0.25
        const labelY = y + r + fontSize * 0.9
        ctx.fillStyle = 'rgba(5,10,20,0.72)'
        ctx.beginPath()
        ctx.roundRect(
          x - textWidth / 2 - padX,
          labelY - padY - fontSize / 2,
          textWidth + padX * 2,
          fontSize + padY * 2,
          3 / globalScale
        )
        ctx.fill()

        ctx.fillStyle = isSelected ? '#ff8a3d' : isFocused ? '#ffffff' : '#c8f0ff'
        ctx.fillText(label, x, labelY)
      }
    },
    [neighbourSet, repaintTick]
  )

  // ── Link color ────────────────────────────────────────────────────────────
  const linkColor = useCallback(
    (link: any) => {
      const { focusedEdge, selectedEdge } = useGraphStore.getState()
      const id = link.dynamicId ?? link.id
      const src = typeof link.source === 'object' ? link.source.id : link.source
      const tgt = typeof link.target === 'object' ? link.target.id : link.target

      if (id === selectedEdge) return '#ff8a3d'
      if (id === focusedEdge) return '#ffffff'

      // Dim links that don't connect to selected node
      if (neighbourSet) {
        const connected = neighbourSet.has(src) && neighbourSet.has(tgt)
        if (!connected) return 'rgba(60,80,110,0.18)'
        return '#00e0ff'
      }
      return '#00e0ff'
    },
    [neighbourSet, repaintTick]
  )

  const linkWidth = useCallback((link: any) => {
    const { focusedEdge, selectedEdge } = useGraphStore.getState()
    const id = link.dynamicId ?? link.id
    if (id === selectedEdge) return 2
    if (id === focusedEdge) return 1.5
    return 0.8
  }, [])

  // ── Custom link painter: curved arc that stops at node edges ─────────────
  const linkCanvasObject = useCallback(
    (link: any, ctx: CanvasRenderingContext2D) => {
      const source = link.source
      const target = link.target
      if (!source || !target) return

      const sx: number = source.x ?? 0
      const sy: number = source.y ?? 0
      const tx: number = target.x ?? 0
      const ty: number = target.y ?? 0
      const sr: number = source.size ?? 6
      const tr: number = target.size ?? 6

      // Self-loop: skip
      if (source.id === target.id) return

      const dx = tx - sx
      const dy = ty - sy
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist === 0) return

      // Unit vector from source to target
      const ux = dx / dist
      const uy = dy / dist

      // Start/end points offset by node radius so line starts at node edge
      const x1 = sx + ux * sr
      const y1 = sy + uy * sr
      const x2 = tx - ux * tr
      const y2 = ty - uy * tr

      // Curvature control point (perpendicular offset = 25% of distance)
      const curvature = 0.25
      const mx = (x1 + x2) / 2
      const my = (y1 + y2) / 2
      // Perpendicular direction
      const px = -uy
      const py = ux
      const offset = dist * curvature * 0.5
      const cpx = mx + px * offset
      const cpy = my + py * offset

      // Determine color and width
      const { focusedEdge, selectedEdge } = useGraphStore.getState()
      const id = link.dynamicId ?? link.id
      const src = typeof link.source === 'object' ? link.source.id : link.source
      const tgt = typeof link.target === 'object' ? link.target.id : link.target

      let color: string
      let width: number

      if (id === selectedEdge) {
        color = '#ff8a3d'
        width = 2
      } else if (id === focusedEdge) {
        color = '#ffffff'
        width = 1.5
      } else if (neighbourSet) {
        const connected = neighbourSet.has(src) && neighbourSet.has(tgt)
        color = connected ? '#00e0ff' : 'rgba(60,80,110,0.15)'
        width = connected ? 0.8 : 0.4
      } else {
        color = '#00e0ff'
        width = 0.8
      }

      ctx.save()
      ctx.beginPath()
      ctx.moveTo(x1, y1)
      ctx.quadraticCurveTo(cpx, cpy, x2, y2)
      ctx.strokeStyle = color
      ctx.lineWidth = width
      ctx.stroke()
      ctx.restore()
    },
    [neighbourSet, repaintTick]
  )

  // ── Event handlers ─────────────────────────────────────────────────────
  const handleNodeClick = useCallback((node: any) => {
    const { selectedNode: cur, setSelectedNode, setFocusedNode, clearSelection } =
      useGraphStore.getState()
    // Toggle: clicking the same node deselects
    if (cur === node.id) {
      clearSelection()
    } else {
      setSelectedNode(node.id)
      setFocusedNode(node.id)
    }
  }, [])

  const handleNodeHover = useCallback((node: any) => {
    useGraphStore.getState().setFocusedNode(node?.id ?? null)
    if (containerRef.current) {
      containerRef.current.style.cursor = node ? 'pointer' : 'default'
    }
  }, [])

  const handleLinkHover = useCallback((link: any) => {
    useGraphStore.getState().setFocusedEdge(link?.dynamicId ?? link?.id ?? null)
  }, [])

  const handleLinkClick = useCallback((link: any) => {
    const { setSelectedEdge, setSelectedNode } = useGraphStore.getState()
    setSelectedEdge(link.dynamicId ?? link.id)
    setSelectedNode(null)
  }, [])

  const handleBackgroundClick = useCallback(() => {
    useGraphStore.getState().clearSelection()
  }, [])

  // ── Search ─────────────────────────────────────────────────────────────
  const onSearchFocus = useCallback((value: SearchOptionItem | null) => {
    if (value === null) useGraphStore.getState().setFocusedNode(null)
    else if (value.type === 'nodes') useGraphStore.getState().setFocusedNode(value.id)
  }, [])

  const onSearchSelect = useCallback((value: SearchOptionItem | null) => {
    if (value === null) useGraphStore.getState().setSelectedNode(null)
    else if (value.type === 'nodes') useGraphStore.getState().setSelectedNode(value.id, true)
  }, [])

  const searchInitSelectedNode = useMemo(
    () => (selectedNode ? { type: 'nodes' as const, id: selectedNode } : null),
    [selectedNode]
  )

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div
      ref={containerRef}
      className="relative h-full w-full overflow-hidden"
      style={{ background: '#050a14' }}
    >
      {/* ── 2D Force Graph ──────────────────────────────────────────────── */}
      <ForceGraph2D
        ref={fgRef as any}
        graphData={graphData}
        backgroundColor="#050a14"
        width={dimensions.width}
        height={dimensions.height}
        // Node
        nodeCanvasObject={nodeCanvasObject}
        nodeCanvasObjectMode={() => 'replace'}
        nodeLabel={(node: any) => node.label || node.id}
        nodeRelSize={1}
        nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
          // Hit area = full circle radius so clicking anywhere on the node works
          ctx.beginPath()
          ctx.arc(node.x ?? 0, node.y ?? 0, (node.size ?? 6) + 2, 0, Math.PI * 2)
          ctx.fillStyle = color
          ctx.fill()
        }}
        // Link – custom curved painter stopping at node edges
        linkCanvasObject={linkCanvasObject}
        linkCanvasObjectMode={() => 'replace'}
        linkWidth={linkWidth}
        linkColor={linkColor}
        // Events
        onNodeClick={handleNodeClick}
        onNodeHover={handleNodeHover}
        onLinkHover={handleLinkHover}
        onLinkClick={handleLinkClick}
        onBackgroundClick={handleBackgroundClick}
      />

      {/* ── Physics configuration (invisible) ──────────────────────────── */}
      <GraphControl fgRef={fgRef} graphData={graphData} />

      {/* ── Top-left: label selector + search ──────────────────────────── */}
      <div className="absolute top-2 left-2 z-10 flex items-start gap-2">
        <GraphLabels />
        {showNodeSearchBar && (
          <GraphSearch
            value={searchInitSelectedNode}
            onFocus={onSearchFocus}
            onChange={onSearchSelect}
          />
        )}
      </div>

      {/* ── Bottom-left: controls ───────────────────────────────────────── */}
      <div className="absolute bottom-2 left-2 z-10 flex flex-col rounded-xl border border-cyan-400/30 bg-slate-950/55 shadow-[0_0_26px_rgba(56,189,248,0.22)] backdrop-blur-xl">
        <LayoutsControl fgRef={fgRef} />
        <ZoomControl fgRef={fgRef} />
        <FullScreenControl containerRef={containerRef} />
        <LegendButton />
        <Settings />
      </div>

      {/* ── Right: properties panel ─────────────────────────────────────── */}
      {showPropertyPanel && (
        <div className="absolute top-2 right-2 z-10">
          <PropertiesView />
        </div>
      )}

      {/* ── Bottom-right: legend ────────────────────────────────────────── */}
      {showLegend && (
        <div className="absolute bottom-10 right-2 z-0">
          <Legend className="border border-cyan-400/30 bg-slate-950/55 shadow-[0_0_24px_rgba(56,189,248,0.2)] backdrop-blur-xl" />
        </div>
      )}

      <SettingsDisplay />

      {/* ── Loading overlay ──────────────────────────────────────────────── */}
      {isFetching && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm">
          <div className="text-center">
            <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-cyan-400 border-t-transparent" />
            <p className="text-sm text-cyan-300">Loading Graph Data...</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default GraphViewer
