import { Fragment, useRef } from 'react'
import { ImageOverlay, Marker, Polygon, Polyline, Popup, Rectangle, Tooltip } from 'react-leaflet'
import L from 'leaflet'
import { FEATURE_COLORS, type MapFeature, type MapMode, type ToolType } from '../model/types'
import { baseIcon, dimensionLabel, moveIcon, qrIcon, vertexIcon, waypointIcon } from '../lib/icons'

interface FeatureLayersProps {
  features: MapFeature[]
  currentPoints: L.LatLngTuple[]
  activeTool: ToolType
  mapMode: MapMode
  editMode: boolean
  showDimensions: boolean
  showAnchors: boolean
  selectedFeatureId: string | null
  onVertexDrag: (featureId: string, index: number, pos: L.LatLngTuple) => void
  onInsertVertex: (featureId: string, index: number, pos: L.LatLngTuple) => void
  onDeleteFeature: (featureId: string) => void
  onDeleteVertex: (featureId: string, index: number) => void
  onMoveFeature: (featureId: string, delta: L.LatLngTuple) => void
  onSelectFeature: (featureId: string) => void
}

function distanceMeters(a: L.LatLngTuple, b: L.LatLngTuple, mapMode: MapMode): number {
  if (mapMode === 'geo') {
    return L.latLng(a).distanceTo(L.latLng(b))
  }
  return Math.hypot(a[0] - b[0], a[1] - b[1])
}

function midpoint(a: L.LatLngTuple, b: L.LatLngTuple): L.LatLngTuple {
  return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
}

function centroid(positions: L.LatLngTuple[]): L.LatLngTuple {
  const n = positions.length
  const sum = positions.reduce<L.LatLngTuple>((acc, [lat, lng]) => [acc[0] + lat, acc[1] + lng], [0, 0])
  return [sum[0] / n, sum[1] / n]
}

function toMeters(positions: L.LatLngTuple[], mapMode: MapMode): [number, number][] {
  if (mapMode === 'relative') {
    return positions.map(([lat, lng]) => [lng, lat])
  }
  const R = 6378137
  const lat0 = (positions[0][0] * Math.PI) / 180
  return positions.map(([lat, lng]) => [(lng * Math.PI) / 180 * R * Math.cos(lat0), (lat * Math.PI) / 180 * R])
}

function shoelaceArea(points: [number, number][]): number {
  let sum = 0
  for (let i = 0; i < points.length; i++) {
    const [x1, y1] = points[i]
    const [x2, y2] = points[(i + 1) % points.length]
    sum += x1 * y2 - x2 * y1
  }
  return Math.abs(sum) / 2
}

function pointToSegmentDistance(p: L.LatLngTuple, a: L.LatLngTuple, b: L.LatLngTuple): number {
  const dx = b[0] - a[0]
  const dy = b[1] - a[1]
  const lengthSq = dx * dx + dy * dy
  if (lengthSq === 0) return Math.hypot(p[0] - a[0], p[1] - a[1])
  let t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / lengthSq
  t = Math.max(0, Math.min(1, t))
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))
}

/** Returns the index at which a new vertex clicked on the nearest edge should be inserted. */
function nearestEdgeInsertIndex(positions: L.LatLngTuple[], isPolygon: boolean, click: L.LatLngTuple): number {
  const n = positions.length
  const edgeCount = isPolygon ? n : n - 1
  let minDist = Infinity
  let insertIndex = n
  for (let i = 0; i < edgeCount; i++) {
    const a = positions[i]
    const b = positions[(i + 1) % n]
    const dist = pointToSegmentDistance(click, a, b)
    if (dist < minDist) {
      minDist = dist
      insertIndex = i + 1
    }
  }
  return insertIndex
}

function DimensionLabels({ positions, isPolygon, mapMode }: { positions: L.LatLngTuple[]; isPolygon: boolean; mapMode: MapMode }) {
  const edges: [L.LatLngTuple, L.LatLngTuple][] = []
  for (let i = 0; i < positions.length - 1; i++) edges.push([positions[i], positions[i + 1]])
  if (isPolygon && positions.length > 2) edges.push([positions[positions.length - 1], positions[0]])

  return (
    <>
      {edges.map(([a, b], idx) => (
        <Marker key={`dim-${idx}`} position={midpoint(a, b)} icon={dimensionLabel(`${distanceMeters(a, b, mapMode).toFixed(2)} м`)} interactive={false} />
      ))}
      {isPolygon && positions.length > 2 && (
        <Marker
          position={centroid(positions)}
          icon={dimensionLabel(`${shoelaceArea(toMeters(positions, mapMode)).toFixed(1)} м²`)}
          interactive={false}
        />
      )}
    </>
  )
}

function VertexMarkers({
  positions,
  isPolygon,
  editMode,
  idPrefix,
  onDrag,
  onDelete,
}: {
  positions: L.LatLngTuple[]
  isPolygon: boolean
  editMode: boolean
  idPrefix: string
  onDrag: (index: number, pos: L.LatLngTuple) => void
  onDelete?: (index: number) => void
}) {
  return (
    <>
      {positions.map((pos, idx) => {
        const isEndpoint = isPolygon ? idx === 0 : idx === 0 || idx === positions.length - 1
        return (
          <Marker
            key={`${idPrefix}-v-${idx}`}
            position={pos}
            icon={vertexIcon(isEndpoint, editMode)}
            draggable={editMode}
            eventHandlers={
              editMode
                ? {
                    dragend: (e) => {
                      const ll = (e.target as L.Marker).getLatLng()
                      onDrag(idx, [ll.lat, ll.lng])
                    },
                    contextmenu: (e) => {
                      L.DomEvent.stopPropagation(e)
                      onDelete?.(idx)
                    },
                  }
                : undefined
            }
          />
        )
      })}
    </>
  )
}

function MoveCentroidMarker({
  positions,
  featureId,
  onMove,
}: {
  positions: L.LatLngTuple[]
  featureId: string
  onMove: (featureId: string, delta: L.LatLngTuple) => void
}) {
  const startRef = useRef<L.LatLng | null>(null)
  const center = centroid(positions)
  return (
    <Marker
      position={center}
      icon={moveIcon}
      draggable
      eventHandlers={{
        dragstart: (e) => { startRef.current = (e.target as L.Marker).getLatLng() },
        dragend: (e) => {
          const end = (e.target as L.Marker).getLatLng()
          if (!startRef.current) return
          onMove(featureId, [end.lat - startRef.current.lat, end.lng - startRef.current.lng])
          startRef.current = null
        },
      }}
    />
  )
}

export function FeatureLayers({
  features,
  currentPoints,
  activeTool,
  mapMode,
  editMode,
  showDimensions,
  showAnchors,
  selectedFeatureId,
  onVertexDrag,
  onInsertVertex,
  onDeleteFeature,
  onDeleteVertex,
  onMoveFeature,
  onSelectFeature,
}: FeatureLayersProps) {
  // Single click: select or delete
  const handleShapeClick = (f: MapFeature) => (e: L.LeafletMouseEvent) => {
    L.DomEvent.stopPropagation(e)
    if (activeTool === 'delete') {
      onDeleteFeature(f.id)
    } else {
      onSelectFeature(f.id)
    }
  }

  // Double click on selected shape: insert vertex on the nearest edge
  const handleShapeDblClick = (f: MapFeature, isPolygon: boolean) => (e: L.LeafletMouseEvent) => {
    L.DomEvent.stopPropagation(e)
    // Also stop DOM propagation to prevent map double-click zoom
    e.originalEvent.stopPropagation()
    e.originalEvent.preventDefault()
    if (!editMode || f.id !== selectedFeatureId) return
    const click: L.LatLngTuple = [e.latlng.lat, e.latlng.lng]
    onInsertVertex(f.id, nearestEdgeInsertIndex(f.positions, isPolygon, click), click)
  }

  const handlePointClick = (f: MapFeature) => (e: L.LeafletMouseEvent) => {
    L.DomEvent.stopPropagation(e)
    if (activeTool === 'delete') {
      onDeleteFeature(f.id)
    } else {
      onSelectFeature(f.id)
    }
  }

  return (
    <>
      {/* Floor-plan images are rendered first so other objects appear on top of them */}
      {features
        .filter((f) => f.type === 'image')
        .filter((f) => f.positions.length >= 2)
        .map((f) => {
          // positions[0]=SW(minLat,minLng), positions[1]=NE(maxLat,maxLng)
          const [sw, ne] = f.positions
          const nw: L.LatLngTuple = [ne[0], sw[1]]
          const se: L.LatLngTuple = [sw[0], ne[1]]
          // 4 corners: SW(0), NW(1), NE(2), SE(3)
          const corners: L.LatLngTuple[] = [sw, nw, ne, se]
          const bounds: L.LatLngBoundsExpression = [sw, ne]

          const handleCornerDrag = (cornerIdx: number, pos: L.LatLngTuple) => {
            // Each corner drag must maintain the opposite corner and update the two shared ones
            // SW(0)↔NE(2), NW(1)↔SE(3)
            let newSw = sw
            let newNe = ne
            if (cornerIdx === 0) { newSw = pos; newNe = ne }
            else if (cornerIdx === 1) { newSw = [sw[0], pos[1]]; newNe = [pos[0], ne[1]] }
            else if (cornerIdx === 2) { newNe = pos; newSw = sw }
            else { newSw = [pos[0], sw[1]]; newNe = [ne[0], pos[1]] }
            onVertexDrag(f.id, 0, [Math.min(newSw[0], newNe[0]), Math.min(newSw[1], newNe[1])])
            onVertexDrag(f.id, 1, [Math.max(newSw[0], newNe[0]), Math.max(newSw[1], newNe[1])])
          }

          return (
            <Fragment key={f.id}>
              {f.imageUrl && (
                <ImageOverlay
                  url={f.imageUrl}
                  bounds={bounds}
                  opacity={0.85}
                  eventHandlers={{
                    click: (e) => {
                      if (activeTool === 'delete') {
                        L.DomEvent.stopPropagation(e)
                        onDeleteFeature(f.id)
                      }
                    },
                  }}
                />
              )}
              {f.id === selectedFeatureId && <Rectangle bounds={bounds} pathOptions={{ color: '#fab005', weight: 2, dashArray: '4 4', fill: false }} interactive={false} />}
              {editMode && showAnchors && (
                <VertexMarkers
                  positions={corners}
                  isPolygon={false}
                  editMode={editMode}
                  idPrefix={f.id}
                  onDrag={handleCornerDrag}
                />
              )}
              {activeTool === 'move' && f.id === selectedFeatureId && (
                <MoveCentroidMarker positions={f.positions} featureId={f.id} onMove={onMoveFeature} />
              )}
            </Fragment>
          )
        })}

      {features
        .filter((f) => f.type !== 'image')
        .filter((f) => f.positions.length >= 1)
        .map((f) => {
          const color = FEATURE_COLORS[f.type]

          if (f.positions.length === 1) {
            const icon = f.type === 'qr' ? qrIcon : f.type === 'base' ? baseIcon : waypointIcon
            return (
              <Fragment key={f.id}>
                <Marker position={f.positions[0]} icon={icon} eventHandlers={{ click: handlePointClick(f) }}>
                  <Popup>
                    {f.label ?? f.id}
                  </Popup>
                </Marker>
                {f.id === selectedFeatureId && (
                  <Marker position={f.positions[0]} icon={vertexIcon(true, false)} interactive={false} />
                )}
              </Fragment>
            )
          }

          const isPolygon = f.type === 'zone' || f.type === 'base'
          if (!isPolygon && f.positions.length < 2) return null

          return (
            <Fragment key={f.id}>
              {isPolygon ? (
                <Polygon
                  positions={f.positions}
                  pathOptions={{
                    color: f.isRoom ? '#339af0' : color,
                    weight: f.isRoom ? 3 : 2,
                    dashArray: f.type === 'base' ? '6' : undefined,
                    fillOpacity: f.isRoom ? 0.12 : 0.15,
                  }}
                  eventHandlers={{ click: handleShapeClick(f), dblclick: handleShapeDblClick(f, true) }}
                >
                  {f.label && <Tooltip>{f.label}</Tooltip>}
                </Polygon>
              ) : (
                <Polyline
                  positions={f.positions}
                  pathOptions={{ color }}
                  eventHandlers={{ click: handleShapeClick(f), dblclick: handleShapeDblClick(f, false) }}
                />
              )}

              {f.id === selectedFeatureId &&
                (isPolygon ? (
                  <Polygon positions={f.positions} pathOptions={{ color: '#fab005', weight: 4, dashArray: '4 4', fill: false }} interactive={false} />
                ) : (
                  <Polyline positions={f.positions} pathOptions={{ color: '#fab005', weight: 5, opacity: 0.6, dashArray: '4 4' }} interactive={false} />
                ))}

              {showDimensions && <DimensionLabels positions={f.positions} isPolygon={isPolygon} mapMode={mapMode} />}

              {showAnchors && (
                <VertexMarkers
                  positions={f.positions}
                  isPolygon={isPolygon}
                  editMode={editMode}
                  idPrefix={f.id}
                  onDrag={(idx, pos) => onVertexDrag(f.id, idx, pos)}
                  onDelete={(idx) => onDeleteVertex(f.id, idx)}
                />
              )}
              {activeTool === 'move' && f.id === selectedFeatureId && (
                <MoveCentroidMarker positions={f.positions} featureId={f.id} onMove={onMoveFeature} />
              )}
            </Fragment>
          )
        })}

      {currentPoints.length > 0 && (
        <>
          {currentPoints.length > 1 && (
            <Polyline positions={currentPoints} pathOptions={{ color: FEATURE_COLORS[activeTool], dashArray: '6' }} />
          )}
          {showAnchors && (
            <VertexMarkers
              positions={currentPoints}
              isPolygon={false}
              editMode={editMode}
              idPrefix="current"
              onDrag={(idx, pos) => onVertexDrag('current', idx, pos)}
            />
          )}
        </>
      )}
    </>
  )
}
