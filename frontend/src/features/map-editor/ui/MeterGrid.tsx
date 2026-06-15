import { useEffect, useState } from 'react'
import { Marker, Polyline, useMap, useMapEvents } from 'react-leaflet'
import { axisLabel } from '../lib/icons'

export function MeterGrid() {
  const map = useMap()
  const [bounds, setBounds] = useState(() => map.getBounds())

  useMapEvents({
    moveend: () => setBounds(map.getBounds()),
    zoomend: () => setBounds(map.getBounds()),
  })

  useEffect(() => {
    setBounds(map.getBounds())
  }, [map])

  const minX = Math.floor(bounds.getWest())
  const maxX = Math.ceil(bounds.getEast())
  const minY = Math.floor(bounds.getSouth())
  const maxY = Math.ceil(bounds.getNorth())

  const verticals: number[] = []
  for (let x = minX; x <= maxX; x++) verticals.push(x)
  const horizontals: number[] = []
  for (let y = minY; y <= maxY; y++) horizontals.push(y)

  return (
    <>
      {verticals.map((x) => {
        const major = x % 5 === 0
        return (
          <Polyline
            key={`v-${x}`}
            positions={[
              [minY, x],
              [maxY, x],
            ]}
            pathOptions={{ color: major ? '#495057' : '#343a40', weight: major ? 1.5 : 0.5, opacity: major ? 0.8 : 0.4, interactive: false }}
          />
        )
      })}
      {horizontals.map((y) => {
        const major = y % 5 === 0
        return (
          <Polyline
            key={`h-${y}`}
            positions={[
              [y, minX],
              [y, maxX],
            ]}
            pathOptions={{ color: major ? '#495057' : '#343a40', weight: major ? 1.5 : 0.5, opacity: major ? 0.8 : 0.4, interactive: false }}
          />
        )
      })}
      {verticals
        .filter((x) => x % 5 === 0)
        .map((x) => <Marker key={`vl-${x}`} position={[minY, x]} icon={axisLabel(`${x} м`)} interactive={false} />)}
      {horizontals
        .filter((y) => y % 5 === 0)
        .map((y) => <Marker key={`hl-${y}`} position={[y, minX]} icon={axisLabel(`${y} м`)} interactive={false} />)}
    </>
  )
}
