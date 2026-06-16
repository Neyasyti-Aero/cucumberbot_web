import type L from 'leaflet'

/**
 * Computes new image SW/NE bounds from 2 reference points.
 * imagePoints: [fracX, fracY] 0-1 fractions of image size (x right, y down).
 * mapPoints: [lat, lng] — where those image points land on the map.
 */
export function applyImageCalibration(
  imagePoints: [number, number][],
  mapPoints: L.LatLngTuple[],
): [L.LatLngTuple, L.LatLngTuple] | null {
  if (imagePoints.length < 2 || mapPoints.length < 2) return null

  const [ip1, ip2] = imagePoints
  const [mp1, mp2] = mapPoints

  const dy = ip2[1] - ip1[1] // vertical fraction difference (image y increases downward)
  const dx = ip2[0] - ip1[0] // horizontal fraction difference

  // Need both axes to determine full bounds
  if (Math.abs(dy) < 1e-6 || Math.abs(dx) < 1e-6) return null

  // image y=0 → top (high lat), y=1 → bottom (low lat)
  // lat(fracY) = maxLat - fracY * latSpan
  // → latSpan = (mp1[0] - mp2[0]) / (ip2[1] - ip1[1])
  const latSpan = (mp1[0] - mp2[0]) / dy
  const maxLat = mp1[0] + ip1[1] * latSpan
  const minLat = maxLat - latSpan

  // lng(fracX) = minLng + fracX * lngSpan
  // → lngSpan = (mp2[1] - mp1[1]) / (ip2[0] - ip1[0])
  const lngSpan = (mp2[1] - mp1[1]) / dx
  const minLng = mp1[1] - ip1[0] * lngSpan
  const maxLng = minLng + lngSpan

  const sw: L.LatLngTuple = [Math.min(minLat, maxLat), Math.min(minLng, maxLng)]
  const ne: L.LatLngTuple = [Math.max(minLat, maxLat), Math.max(minLng, maxLng)]
  return [sw, ne]
}
