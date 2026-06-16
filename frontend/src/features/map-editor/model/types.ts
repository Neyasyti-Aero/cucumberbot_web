import type L from 'leaflet'

export type ToolType = 'select' | 'zone' | 'path' | 'waypoint' | 'base' | 'qr' | 'delete' | 'image' | 'move'

export type MapMode = 'geo' | 'relative'

export interface MapFeature {
  id: string
  type: ToolType
  positions: L.LatLngTuple[]
  label?: string
  isRoom?: boolean
  /** Storage key of an uploaded floor-plan image (type === 'image') */
  imageKey?: string
  /** Resolved blob URL for rendering the image overlay (runtime-only, not persisted) */
  imageUrl?: string
}

export const FEATURE_COLORS: Record<ToolType, string> = {
  zone: '#40c057',
  path: '#228be6',
  waypoint: '#ae3ec9',
  base: '#fd7e14',
  qr: '#0ca678',
  select: '#868e96',
  delete: '#fa5252',
  image: '#495057',
  move: '#1971c2',
}
