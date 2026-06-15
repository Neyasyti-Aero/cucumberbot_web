import type L from 'leaflet'
import type { MapFeature, MapMode, ToolType } from '../model/types'

type Position = [number, number]

export interface MapGeoJSON {
  type: 'FeatureCollection'
  properties?: { mapMode?: MapMode }
  features: Array<{
    type: 'Feature'
    properties: { featureType: ToolType; label?: string; isRoom?: boolean; imageKey?: string }
    geometry:
      | { type: 'Point'; coordinates: Position }
      | { type: 'Polygon'; coordinates: Position[][] }
      | { type: 'LineString'; coordinates: Position[] }
  }>
}

export function featuresToGeoJSON(features: MapFeature[], mapMode: MapMode): MapGeoJSON {
  return {
    type: 'FeatureCollection',
    properties: { mapMode },
    features: features.map((f) => ({
      type: 'Feature',
      properties: { featureType: f.type, label: f.label, isRoom: f.isRoom, imageKey: f.imageKey },
      geometry:
        f.type === 'image'
          ? (() => {
              const [[latA, lngA], [latB, lngB]] = f.positions
              const minLat = Math.min(latA, latB)
              const maxLat = Math.max(latA, latB)
              const minLng = Math.min(lngA, lngB)
              const maxLng = Math.max(lngA, lngB)
              return {
                type: 'Polygon' as const,
                coordinates: [
                  [
                    [minLng, minLat],
                    [maxLng, minLat],
                    [maxLng, maxLat],
                    [minLng, maxLat],
                    [minLng, minLat],
                  ] as Position[],
                ],
              }
            })()
          : f.positions.length === 1
            ? { type: 'Point', coordinates: [f.positions[0][1], f.positions[0][0]] }
            : f.type === 'zone' || f.type === 'base'
              ? {
                  type: 'Polygon',
                  coordinates: [[...f.positions.map(([lat, lng]): Position => [lng, lat]), [f.positions[0][1], f.positions[0][0]] as Position]],
                }
              : { type: 'LineString', coordinates: f.positions.map(([lat, lng]): Position => [lng, lat]) },
    })),
  }
}

export function geoJSONToFeatures(geojson: MapGeoJSON, nextId: () => string): MapFeature[] {
  return geojson.features.map((feature) => {
    const props = feature.properties ?? ({} as MapGeoJSON['features'][number]['properties'])

    if (props.featureType === 'image' && feature.geometry.type === 'Polygon') {
      const ring = feature.geometry.coordinates[0]
      const lats = ring.map(([, lat]) => lat)
      const lngs = ring.map(([lng]) => lng)
      const positions: L.LatLngTuple[] = [
        [Math.min(...lats), Math.min(...lngs)],
        [Math.max(...lats), Math.max(...lngs)],
      ]
      return {
        id: nextId(),
        type: 'image',
        positions,
        label: props.label,
        imageKey: props.imageKey,
      }
    }

    let positions: L.LatLngTuple[]
    if (feature.geometry.type === 'Point') {
      const [lng, lat] = feature.geometry.coordinates
      positions = [[lat, lng]]
    } else if (feature.geometry.type === 'Polygon') {
      positions = feature.geometry.coordinates[0].slice(0, -1).map(([lng, lat]): L.LatLngTuple => [lat, lng])
    } else {
      positions = feature.geometry.coordinates.map(([lng, lat]): L.LatLngTuple => [lat, lng])
    }
    return {
      id: nextId(),
      type: props.featureType ?? 'zone',
      positions,
      label: props.label,
      isRoom: props.isRoom,
    }
  })
}
