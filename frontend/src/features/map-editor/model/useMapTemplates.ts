import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { listTemplates } from '../api/templates'
import type { MapMode } from './types'

const STORAGE_PREFIX = 'mapEditor.selectedTemplate.'

export function useMapTemplates(mapMode: MapMode) {
  const queryClient = useQueryClient()
  const [selectedTemplateId, setSelectedTemplateIdState] = useState<string | null>(
    () => localStorage.getItem(`${STORAGE_PREFIX}${mapMode}`),
  )

  useEffect(() => {
    setSelectedTemplateIdState(localStorage.getItem(`${STORAGE_PREFIX}${mapMode}`))
  }, [mapMode])

  const { data: templates = [], isLoading } = useQuery({
    queryKey: ['map-templates', mapMode],
    queryFn: () => listTemplates(mapMode),
  })

  const setSelectedTemplateId = (id: string | null) => {
    setSelectedTemplateIdState(id)
    if (id) {
      localStorage.setItem(`${STORAGE_PREFIX}${mapMode}`, id)
    } else {
      localStorage.removeItem(`${STORAGE_PREFIX}${mapMode}`)
    }
  }

  const refetchTemplates = () => queryClient.invalidateQueries({ queryKey: ['map-templates', mapMode] })

  return { templates, isLoading, selectedTemplateId, setSelectedTemplateId, refetchTemplates }
}
