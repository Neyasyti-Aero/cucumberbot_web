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
  const { data } = await api.post<{ key: string }>('/maps/images', form)
  return data.key
}

export async function getImageBlobUrl(key: string): Promise<string> {
  const { data } = await api.get(`/maps/images/${key}`, { responseType: 'blob' })
  return URL.createObjectURL(data)
}
