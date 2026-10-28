import { api } from '@shared/api/base'
import type { MapMode } from '../model/types'
import type { MapGeoJSON } from '../lib/geojson'

export interface MapTemplate {
  id: string
  name: string
  description: string
  created_at: string
  map_type: MapMode
  width_meters: number | null
  height_meters: number | null
  has_layout: boolean
}

export async function listTemplates(mapType: MapMode): Promise<MapTemplate[]> {
  const { data } = await api.get<MapTemplate[]>('/maps', { params: { map_type: mapType } })
  return data
}

export interface CreateTemplatePayload {
  name: string
  description?: string
  map_type: MapMode
  geojson: MapGeoJSON
  width_meters?: number
  height_meters?: number
}

export async function createTemplate(payload: CreateTemplatePayload): Promise<MapTemplate> {
  const { data } = await api.post<MapTemplate>('/maps/templates', payload)
  return data
}

export interface UpdateLayoutPayload {
  geojson: MapGeoJSON
  name?: string
  description?: string
  width_meters?: number
  height_meters?: number
}

export async function updateLayout(id: string, payload: UpdateLayoutPayload): Promise<MapTemplate> {
  const { data } = await api.put<MapTemplate>(`/maps/${id}/layout`, payload)
  return data
}

export async function getLayout(id: string): Promise<MapGeoJSON> {
  const { data } = await api.get<MapGeoJSON>(`/maps/${id}/layout`)
  return data
}

export async function uploadImage(file: File): Promise<string> {
  const form = new FormData()
  form.append('file', file)
  // Unset the axios default Content-Type so the browser sets multipart/form-data with the correct boundary
  const { data } = await api.post<{ key: string }>('/maps/images', form, {
    headers: { 'Content-Type': undefined },
  })
  return data.key
}

/** Скачивает бинарный ответ API как файл (нужен Authorization, поэтому не обычная ссылка) */
async function downloadFile(url: string, filename: string, method: 'get' | 'post' = 'get') {
  const { data } = await api.request({ url, method, responseType: 'blob' })
  const href = URL.createObjectURL(data)
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  a.click()
  URL.revokeObjectURL(href)
}

/** map.pgm + map.yaml для nav2_map_server */
export function downloadNav2Map(id: string) {
  return downloadFile(`/maps/${id}/nav2.zip`, `map_${id}.zip`)
}

export interface Nav2Report {
  valid: boolean
  errors: string[]
  warnings: string[]
  width: number
  height: number
  resolution: number
}

export async function validateNav2Map(id: string): Promise<Nav2Report> {
  const { data } = await api.get<Nav2Report>(`/maps/${id}/nav2/validate`)
  return data
}

/** Создаёт метки для QR-точек карты и скачивает PDF для печати */
export async function generateQrSheet(id: string, sizeMm = 50): Promise<number> {
  const { data } = await api.post<{ created: unknown[]; kept: unknown[] }>(`/qr/maps/${id}/sync`)
  const total = data.created.length + data.kept.length
  if (total > 0) await downloadFile(`/qr/maps/${id}/sheet.pdf?size_mm=${sizeMm}`, `qr_${id}.pdf`)
  return total
}

export async function getImageBlobUrl(key: string): Promise<string> {
  const { data } = await api.get(`/maps/images/${key}`, { responseType: 'blob' })
  return URL.createObjectURL(data)
}
