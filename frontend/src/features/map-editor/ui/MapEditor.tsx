import {
  ActionIcon,
  Button,
  Group,
  Modal,
  NumberInput,
  Paper,
  ScrollArea,
  SegmentedControl,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
  Tooltip,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  IconCursorText,
  IconPolygon,
  IconRoute,
  IconMapPin,
  IconHome,
  IconQrcode,
  IconTrash,
  IconEdit,
  IconEye,
  IconRuler,
  IconAxisX,
  IconDeviceFloppy,
  IconFilePlus,
  IconPhoto,
  IconPhotoPlus,
  IconCrosshair,
  IconArrowsMove,
  IconRectangle,
  IconRuler2,
} from '@tabler/icons-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { MapContainer, Marker, Polyline, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

import type { MapFeature, MapMode, ToolType } from '../model/types'
import { FEATURE_COLORS } from '../model/types'
import { FeatureLayers } from './FeatureLayers'
import { MeterGrid } from './MeterGrid'
import { featuresToGeoJSON, geoJSONToFeatures } from '../lib/geojson'
import { createTemplate, getImageBlobUrl, getLayout, updateLayout, uploadImage } from '../api/templates'
import { useMapTemplates } from '../model/useMapTemplates'
import { applyImageCalibration } from '../lib/calibration'
import { calibPointIcon, dimensionLabel } from '../lib/icons'
import { ImageCalibModal } from './ImageCalibModal'

delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

const TOOLS: { key: ToolType; icon: React.ReactNode; color?: string }[] = [
  { key: 'select', icon: <IconCursorText size={18} /> },
  { key: 'move', icon: <IconArrowsMove size={18} />, color: 'blue' },
  { key: 'zone', icon: <IconPolygon size={18} />, color: 'green' },
  { key: 'path', icon: <IconRoute size={18} />, color: 'blue' },
  { key: 'waypoint', icon: <IconMapPin size={18} />, color: 'grape' },
  { key: 'base', icon: <IconHome size={18} />, color: 'orange' },
  { key: 'qr', icon: <IconQrcode size={18} />, color: 'teal' },
  { key: 'delete', icon: <IconTrash size={18} />, color: 'red' },
]

const OBJECT_TYPE_ICONS: Record<ToolType, React.ReactNode> = {
  select: <IconCursorText size={14} />,
  move: <IconArrowsMove size={14} />,
  zone: <IconPolygon size={14} />,
  path: <IconRoute size={14} />,
  waypoint: <IconMapPin size={14} />,
  base: <IconHome size={14} />,
  qr: <IconQrcode size={14} />,
  delete: <IconTrash size={14} />,
  image: <IconPhoto size={14} />,
}

const GEO_CENTER: L.LatLngTuple = [55.75, 37.62]
const RELATIVE_CENTER: L.LatLngTuple = [10, 10]

function MapEventHandler({
  activeTool,
  editMode,
  onAddPoint,
  isCalibStep2,
  onCalibMapPoint,
}: {
  activeTool: ToolType
  editMode: boolean
  onAddPoint: (pos: L.LatLngTuple) => void
  isCalibStep2: boolean
  onCalibMapPoint: (pos: L.LatLngTuple) => void
}) {
  useMapEvents({
    click(e) {
      if (isCalibStep2) {
        onCalibMapPoint([e.latlng.lat, e.latlng.lng])
        return
      }
      if (!editMode) return
      if (activeTool !== 'select' && activeTool !== 'delete' && activeTool !== 'move') {
        onAddPoint([e.latlng.lat, e.latlng.lng])
      }
    },
  })
  return null
}

function FitBounds({ bounds }: { bounds: L.LatLngBoundsExpression | null }) {
  const map = useMap()
  useEffect(() => {
    if (bounds) map.fitBounds(bounds, { padding: [20, 20] })
  }, [map, bounds])
  return null
}

export function MapEditor() {
  const { t } = useTranslation()
  const [mapMode, setMapMode] = useState<MapMode>('geo')
  const [activeTool, setActiveTool] = useState<ToolType>('select')
  const [features, setFeatures] = useState<MapFeature[]>([])
  const [currentPoints, setCurrentPoints] = useState<L.LatLngTuple[]>([])
  const [editMode, setEditMode] = useState(true)
  const [showDimensions, setShowDimensions] = useState(false)
  const [showAnchors, setShowAnchors] = useState(true)
  const [presetRectEnabled, setPresetRectEnabled] = useState(false)
  const [presetRectW, setPresetRectW] = useState<number | string>(2)
  const [presetRectH, setPresetRectH] = useState<number | string>(1)
  const [fitBounds, setFitBounds] = useState<L.LatLngBoundsExpression | null>(null)
  const [selectedFeatureId, setSelectedFeatureId] = useState<string | null>(null)
  const [roomWidth, setRoomWidth] = useState<number | string>(10)
  const [roomHeight, setRoomHeight] = useState<number | string>(8)
  const [bedX, setBedX] = useState<number | string>(1)
  const [bedY, setBedY] = useState<number | string>(1)
  const [bedWidth, setBedWidth] = useState<number | string>(2)
  const [bedHeight, setBedHeight] = useState<number | string>(1)
  type CalibState = {
    imageFeatureId: string
    step: 1 | 2
    imagePoints: [number, number][]
    mapPoints: L.LatLngTuple[]
  }
  const [calibState, setCalibState] = useState<CalibState | null>(null)

  const idRef = useRef(0)
  const mapRef = useRef<L.Map | null>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)

  const { templates, selectedTemplateId, setSelectedTemplateId, refetchTemplates } = useMapTemplates(mapMode)
  const [saveModalOpened, { open: openSaveModal, close: closeSaveModal }] = useDisclosure(false)
  const saveForm = useForm({
    initialValues: { name: '', description: '' },
    validate: { name: (v) => (v.trim() ? null : 'Введите название') },
  })

  useEffect(() => {
    setFitBounds(null)
    setFeatures([])
    setCurrentPoints([])
    setSelectedFeatureId(null)
  }, [mapMode])

  useEffect(() => {
    if (!selectedTemplateId) return
    let ignore = false
    getLayout(selectedTemplateId)
      .then((geojson) => {
        if (ignore) return
        const loaded = geoJSONToFeatures(geojson, () => String(++idRef.current))
        setFeatures(loaded)
        setCurrentPoints([])
        setSelectedFeatureId(null)
        const room = loaded.find((f) => f.isRoom)
        if (room) {
          const w = Math.max(...room.positions.map((p) => p[1]))
          const h = Math.max(...room.positions.map((p) => p[0]))
          setRoomWidth(w)
          setRoomHeight(h)
          setFitBounds(L.latLngBounds([0, 0], [h, w]))
        }

        const imageFeatures = loaded.filter((f) => f.type === 'image' && f.imageKey)
        if (imageFeatures.length > 0) {
          Promise.all(
            imageFeatures.map((f) => getImageBlobUrl(f.imageKey as string).then((url) => ({ id: f.id, url }))),
          ).then((resolved) => {
            if (ignore) return
            setFeatures((prev) =>
              prev.map((f) => {
                const match = resolved.find((r) => r.id === f.id)
                return match ? { ...f, imageUrl: match.url } : f
              }),
            )
          })
        }
      })
      .catch(() => {
        notifications.show({ title: t('map.layoutSaveError'), message: '', color: 'red' })
      })
    return () => {
      ignore = true
    }
  }, [selectedTemplateId])

  const handleAddPoint = useCallback(
    (pos: L.LatLngTuple) => {
      if (activeTool === 'waypoint' || activeTool === 'qr') {
        setFeatures((prev) => [...prev, { id: String(++idRef.current), type: activeTool, positions: [pos] }])
      } else if (activeTool === 'zone' && presetRectEnabled) {
        const w = Number(presetRectW) || 1
        const h = Number(presetRectH) || 1
        const positions: L.LatLngTuple[] = [
          [pos[0] - h / 2, pos[1] - w / 2],
          [pos[0] - h / 2, pos[1] + w / 2],
          [pos[0] + h / 2, pos[1] + w / 2],
          [pos[0] + h / 2, pos[1] - w / 2],
        ]
        setFeatures((prev) => [...prev, { id: String(++idRef.current), type: 'zone', positions }])
      } else {
        setCurrentPoints((prev) => [...prev, pos])
      }
    },
    [activeTool, presetRectEnabled, presetRectW, presetRectH],
  )

  const commitShape = () => {
    const minPoints: Record<ToolType, number> = {
      zone: 3, path: 2, base: 3,
      select: 1, delete: 1, waypoint: 1, qr: 1, image: 1, move: 1,
    }
    const min = minPoints[activeTool] ?? 1
    if (currentPoints.length < min) {
      notifications.show({
        title: t('map.tooFewPoints', { min }),
        message: t('map.tooFewPointsHint', { min }),
        color: 'orange',
      })
      return
    }
    setFeatures((prev) => [...prev, { id: String(++idRef.current), type: activeTool, positions: currentPoints }])
    setCurrentPoints([])
  }

  const handleVertexDrag = useCallback((featureId: string, index: number, pos: L.LatLngTuple) => {
    if (featureId === 'current') {
      setCurrentPoints((prev) => prev.map((p, i) => (i === index ? pos : p)))
      return
    }
    setFeatures((prev) =>
      prev.map((f) => (f.id === featureId ? { ...f, positions: f.positions.map((p, i) => (i === index ? pos : p)) } : f)),
    )
  }, [])

  const handleInsertVertex = useCallback((featureId: string, index: number, pos: L.LatLngTuple) => {
    setFeatures((prev) =>
      prev.map((f) => {
        if (f.id !== featureId) return f
        const positions = [...f.positions]
        positions.splice(index, 0, pos)
        return { ...f, positions }
      }),
    )
  }, [])

  const handleDeleteFeature = useCallback((featureId: string) => {
    setFeatures((prev) => prev.filter((f) => f.id !== featureId))
    setSelectedFeatureId((prev) => (prev === featureId ? null : prev))
  }, [])

  const handleRenameFeature = useCallback((featureId: string, label: string) => {
    setFeatures((prev) => prev.map((f) => (f.id === featureId ? { ...f, label } : f)))
  }, [])

  const handleSelectFeature = useCallback((featureId: string) => {
    setSelectedFeatureId((prev) => (prev === featureId ? null : featureId))
  }, [])

  const handleDeleteVertex = useCallback((featureId: string, index: number) => {
    setFeatures((prev) =>
      prev.map((f) => {
        if (f.id !== featureId) return f
        const positions = f.positions.filter((_, i) => i !== index)
        return { ...f, positions }
      }),
    )
  }, [])

  const handleMoveFeature = useCallback((featureId: string, delta: L.LatLngTuple) => {
    setFeatures((prev) =>
      prev.map((f) =>
        f.id !== featureId
          ? f
          : { ...f, positions: f.positions.map(([lat, lng]) => [lat + delta[0], lng + delta[1]] as L.LatLngTuple) },
      ),
    )
  }, [])

  const handleStartCalib = useCallback((featureId: string) => {
    const f = features.find((ft) => ft.id === featureId)
    if (!f?.imageUrl) return
    setCalibState({ imageFeatureId: featureId, step: 1, imagePoints: [], mapPoints: [] })
  }, [features])

  const handleCalibImagePoint = useCallback((frac: [number, number]) => {
    setCalibState((prev) => {
      if (!prev || prev.step !== 1) return prev
      const pts = [...prev.imagePoints, frac]
      return pts.length >= 2 ? { ...prev, step: 2, imagePoints: pts } : { ...prev, imagePoints: pts }
    })
  }, [])

  const handleCalibMapPoint = useCallback((pos: L.LatLngTuple) => {
    setCalibState((prev) => {
      if (!prev || prev.step !== 2) return prev
      return { ...prev, mapPoints: [...prev.mapPoints, pos] }
    })
  }, [])

  useEffect(() => {
    if (!calibState || calibState.step !== 2 || calibState.mapPoints.length < 2) return
    const result = applyImageCalibration(calibState.imagePoints, calibState.mapPoints)
    if (result) {
      const [sw, ne] = result
      setFeatures((prev) => prev.map((f) => (f.id === calibState.imageFeatureId ? { ...f, positions: [sw, ne] } : f)))
    } else {
      notifications.show({ title: t('map.calibError'), message: '', color: 'orange' })
    }
    setCalibState(null)
  }, [calibState])

  const handleFocusFeature = useCallback((f: MapFeature) => {
    setSelectedFeatureId(f.id)
    const map = mapRef.current
    if (!map) return
    if (f.positions.length === 1) {
      map.panTo(f.positions[0])
    } else {
      map.fitBounds(L.latLngBounds(f.positions), { padding: [40, 40] })
    }
  }, [])

  const handleImageFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    try {
      const key = await uploadImage(file)
      const url = await getImageBlobUrl(key)
      const map = mapRef.current
      let positions: L.LatLngTuple[]
      if (map) {
        const bounds = map.getBounds()
        const center = bounds.getCenter()
        const latSpan = (bounds.getNorth() - bounds.getSouth()) / 2
        const lngSpan = (bounds.getEast() - bounds.getWest()) / 2
        positions = [
          [center.lat - latSpan / 2, center.lng - lngSpan / 2],
          [center.lat + latSpan / 2, center.lng + lngSpan / 2],
        ]
      } else {
        positions =
          mapMode === 'geo'
            ? [
                [GEO_CENTER[0] - 0.001, GEO_CENTER[1] - 0.001],
                [GEO_CENTER[0] + 0.001, GEO_CENTER[1] + 0.001],
              ]
            : [
                [0, 0],
                [10, 10],
              ]
      }
      setFeatures((prev) => [
        ...prev,
        { id: String(++idRef.current), type: 'image', positions, imageKey: key, imageUrl: url, label: file.name },
      ])
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err)
      notifications.show({ title: t('map.imageUploadError'), message: detail, color: 'red' })
    }
  }

  const addRoom = () => {
    const w = Number(roomWidth) || 0
    const h = Number(roomHeight) || 0
    if (w <= 0 || h <= 0) return
    const positions: L.LatLngTuple[] = [
      [0, 0],
      [0, w],
      [h, w],
      [h, 0],
    ]
    setFeatures((prev) => [
      ...prev.filter((f) => !f.isRoom),
      { id: String(++idRef.current), type: 'zone', positions, isRoom: true, label: `${t('map.room')} ${w}×${h} ${t('map.meters')}` },
    ])
    setFitBounds(L.latLngBounds([0, 0], [h, w]))
  }

  const addBed = () => {
    const x = Number(bedX) || 0
    const y = Number(bedY) || 0
    const w = Number(bedWidth) || 0
    const h = Number(bedHeight) || 0
    if (w <= 0 || h <= 0) return
    const positions: L.LatLngTuple[] = [
      [y, x],
      [y, x + w],
      [y + h, x + w],
      [y + h, x],
    ]
    setFeatures((prev) => [...prev, { id: String(++idRef.current), type: 'zone', positions, label: t('map.tools.zone') }])
  }

  const exportGeoJSON = () => {
    const geojson = featuresToGeoJSON(features, mapMode)
    const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'map-layout.geojson'
    a.click()
    URL.revokeObjectURL(url)
  }

  const updateMutation = useMutation({
    mutationFn: (id: string) =>
      updateLayout(id, {
        geojson: featuresToGeoJSON(features, mapMode),
        width_meters: mapMode === 'relative' ? Number(roomWidth) || undefined : undefined,
        height_meters: mapMode === 'relative' ? Number(roomHeight) || undefined : undefined,
      }),
    onSuccess: () => {
      notifications.show({ title: t('map.layoutSaved'), message: '', color: 'green' })
      refetchTemplates()
    },
    onError: () => notifications.show({ title: t('map.layoutSaveError'), message: '', color: 'red' }),
  })

  const createMutation = useMutation({
    mutationFn: (values: { name: string; description: string }) =>
      createTemplate({
        name: values.name,
        description: values.description,
        map_type: mapMode,
        geojson: featuresToGeoJSON(features, mapMode),
        width_meters: mapMode === 'relative' ? Number(roomWidth) || undefined : undefined,
        height_meters: mapMode === 'relative' ? Number(roomHeight) || undefined : undefined,
      }),
    onSuccess: (created) => {
      notifications.show({ title: t('map.templateSaved'), message: '', color: 'green' })
      setSelectedTemplateId(created.id)
      refetchTemplates()
      closeSaveModal()
      saveForm.reset()
    },
    onError: () => notifications.show({ title: t('map.templateSaveError'), message: '', color: 'red' }),
  })

  const handleSave = () => {
    if (selectedTemplateId) {
      updateMutation.mutate(selectedTemplateId)
    } else {
      saveForm.setValues({ name: '', description: '' })
      openSaveModal()
    }
  }

  const handleSaveAsNew = () => {
    const current = templates.find((tpl) => tpl.id === selectedTemplateId)
    saveForm.setValues({ name: current ? `${current.name} (копия)` : '', description: current?.description ?? '' })
    openSaveModal()
  }

  return (
    <Stack h="100%" gap="sm">
      <Group justify="space-between" wrap="wrap">
        <Text fw={600} size="lg">
          {t('map.title')}
        </Text>
        <Group gap="xs" wrap="wrap">
          <SegmentedControl
            value={mapMode}
            onChange={(v) => setMapMode(v as MapMode)}
            data={[
              { label: t('map.geoMode'), value: 'geo' },
              { label: t('map.relativeMode'), value: 'relative' },
            ]}
          />
          <Select
            placeholder={t('map.selectTemplate')}
            data={templates.map((tpl) => ({ value: tpl.id, label: tpl.name }))}
            value={selectedTemplateId}
            onChange={setSelectedTemplateId}
            clearable
            searchable
            size="xs"
            w={200}
          />
          {currentPoints.length > 0 && (
            <Button size="xs" variant="light" onClick={commitShape}>
              {t('map.commitShape', { count: currentPoints.length })}
            </Button>
          )}
          <input ref={imageInputRef} type="file" accept="image/*,application/pdf" style={{ display: 'none' }} onChange={handleImageFileChange} />
          <Tooltip label={t('map.uploadPlan')}>
            <ActionIcon variant="light" color="gray" size="lg" onClick={() => imageInputRef.current?.click()}>
              <IconPhotoPlus size={18} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label={t('map.save')}>
            <ActionIcon variant="light" color="blue" size="lg" loading={updateMutation.isPending} onClick={handleSave}>
              <IconDeviceFloppy size={18} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label={t('map.saveAsTemplate')}>
            <ActionIcon variant="light" color="blue" size="lg" onClick={handleSaveAsNew}>
              <IconFilePlus size={18} />
            </ActionIcon>
          </Tooltip>
          <Button size="xs" variant="light" color="teal" onClick={exportGeoJSON}>
            {t('map.export')}
          </Button>
        </Group>
      </Group>

      <Paper withBorder p="xs">
        <Group gap="xs" justify="space-between">
          <Group gap="xs">
            {TOOLS.map(({ key, icon, color }) => (
              <Tooltip key={key} label={t(`map.tools.${key}`)}>
                <ActionIcon
                  variant={activeTool === key ? 'filled' : 'light'}
                  color={color ?? 'gray'}
                  onClick={() => setActiveTool(key)}
                  size="lg"
                >
                  {icon}
                </ActionIcon>
              </Tooltip>
            ))}
          </Group>
          <Group gap="xs">
            <Tooltip label={editMode ? t('map.editMode') : t('map.viewMode')}>
              <ActionIcon variant={editMode ? 'filled' : 'light'} color="blue" size="lg" onClick={() => setEditMode((v) => !v)}>
                {editMode ? <IconEdit size={18} /> : <IconEye size={18} />}
              </ActionIcon>
            </Tooltip>
            <Tooltip label={t('map.showDimensions')}>
              <ActionIcon variant={showDimensions ? 'filled' : 'light'} color="grape" size="lg" onClick={() => setShowDimensions((v) => !v)}>
                <IconRuler size={18} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label={t('map.showAnchors')}>
              <ActionIcon variant={showAnchors ? 'filled' : 'light'} color="grape" size="lg" onClick={() => setShowAnchors((v) => !v)}>
                <IconAxisX size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
      </Paper>

      {activeTool === 'zone' && (
        <Paper withBorder p="xs">
          <Group gap="xs" align="flex-end">
            <Tooltip label={t('map.presetRectToggle')}>
              <ActionIcon
                variant={presetRectEnabled ? 'filled' : 'light'}
                color="green"
                size="lg"
                onClick={() => setPresetRectEnabled((v) => !v)}
              >
                <IconRectangle size={18} />
              </ActionIcon>
            </Tooltip>
            {presetRectEnabled && (
              <>
                <NumberInput
                  label={t('map.presetRectW')}
                  value={presetRectW}
                  onChange={setPresetRectW}
                  min={0.1}
                  step={0.5}
                  w={120}
                  size="xs"
                />
                <NumberInput
                  label={t('map.presetRectH')}
                  value={presetRectH}
                  onChange={setPresetRectH}
                  min={0.1}
                  step={0.5}
                  w={120}
                  size="xs"
                />
                <Text size="xs" c="dimmed" style={{ alignSelf: 'center', marginBottom: 2 }}>
                  {t('map.presetRectHint')}
                </Text>
              </>
            )}
          </Group>
        </Paper>
      )}

      {mapMode === 'relative' && (
        <Paper withBorder p="xs">
          <Group gap="md" wrap="wrap">
            <Group gap="xs" align="flex-end">
              <NumberInput label={t('map.roomWidth')} value={roomWidth} onChange={setRoomWidth} min={0.5} step={0.5} w={130} size="xs" />
              <NumberInput label={t('map.roomHeight')} value={roomHeight} onChange={setRoomHeight} min={0.5} step={0.5} w={130} size="xs" />
              <Button size="xs" onClick={addRoom}>
                {t('map.addRoom')}
              </Button>
            </Group>
            <Group gap="xs" align="flex-end">
              <NumberInput label={t('map.bedX')} value={bedX} onChange={setBedX} step={0.5} w={90} size="xs" />
              <NumberInput label={t('map.bedY')} value={bedY} onChange={setBedY} step={0.5} w={90} size="xs" />
              <NumberInput label={t('map.bedWidth')} value={bedWidth} onChange={setBedWidth} min={0.1} step={0.1} w={90} size="xs" />
              <NumberInput label={t('map.bedHeight')} value={bedHeight} onChange={setBedHeight} min={0.1} step={0.1} w={90} size="xs" />
              <Button size="xs" onClick={addBed}>
                {t('map.addBed')}
              </Button>
            </Group>
          </Group>
        </Paper>
      )}

      {calibState?.step === 2 && (
        <Text size="sm" ta="center" style={{ background: '#e7f5ff', color: '#1971c2', padding: '4px 12px', borderRadius: 4 }}>
          {calibState.mapPoints.length === 0 ? t('map.calibClickMap1') : t('map.calibClickMap2')}
          {' · '}
          <span style={{ cursor: 'pointer', textDecoration: 'underline' }} onClick={() => setCalibState(null)}>
            {t('common.cancel')}
          </span>
        </Text>
      )}

      <Group gap="sm" wrap="nowrap" align="stretch" style={{ flex: 1, minHeight: 500 }}>
        <MapContainer
          key={mapMode}
          ref={mapRef}
          center={mapMode === 'geo' ? GEO_CENTER : RELATIVE_CENTER}
          zoom={mapMode === 'geo' ? 18 : 2}
          minZoom={mapMode === 'geo' ? 0 : -2}
          maxZoom={mapMode === 'geo' ? 21 : 8}
          crs={mapMode === 'geo' ? L.CRS.EPSG3857 : L.CRS.Simple}
          attributionControl={false}
          style={{ flex: 1, minHeight: 500, borderRadius: 8, cursor: calibState?.step === 2 ? 'crosshair' : undefined }}
        >
          {mapMode === 'geo' ? <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={21} maxNativeZoom={19} /> : <MeterGrid />}
          <MapEventHandler
            activeTool={activeTool}
            editMode={editMode}
            onAddPoint={handleAddPoint}
            isCalibStep2={calibState?.step === 2}
            onCalibMapPoint={handleCalibMapPoint}
          />
          <FitBounds bounds={fitBounds} />

          {/* Calibration reference markers (step 2) */}
          {calibState?.step === 2 && calibState.mapPoints.map((pos, i) => (
            <Marker key={`calib-${i}`} position={pos} icon={calibPointIcon((i + 1) as 1 | 2)} interactive={false} />
          ))}
          {calibState?.step === 2 && calibState.mapPoints.length === 2 && (() => {
            const [m1, m2] = calibState.mapPoints
            const mid: L.LatLngTuple = [(m1[0] + m2[0]) / 2, (m1[1] + m2[1]) / 2]
            const dist = mapMode === 'geo' ? L.latLng(m1).distanceTo(L.latLng(m2)) : Math.hypot(m1[0] - m2[0], m1[1] - m2[1])
            return (
              <>
                <Polyline positions={calibState.mapPoints} pathOptions={{ color: '#f03e3e', weight: 2, dashArray: '4 4' }} interactive={false} />
                <Marker position={mid} icon={dimensionLabel(`${dist.toFixed(2)} м`)} interactive={false} />
              </>
            )
          })()}

          <FeatureLayers
            features={features}
            currentPoints={currentPoints}
            activeTool={activeTool}
            mapMode={mapMode}
            editMode={editMode}
            showDimensions={showDimensions}
            showAnchors={showAnchors}
            selectedFeatureId={selectedFeatureId}
            onVertexDrag={handleVertexDrag}
            onInsertVertex={handleInsertVertex}
            onDeleteFeature={handleDeleteFeature}
            onDeleteVertex={handleDeleteVertex}
            onMoveFeature={handleMoveFeature}
            onSelectFeature={handleSelectFeature}
          />
        </MapContainer>

        <Paper withBorder p="xs" w={260} style={{ display: 'flex', flexDirection: 'column' }}>
          <Text fw={600} size="sm" mb="xs">
            {t('map.objects')}
          </Text>
          <ScrollArea style={{ flex: 1 }}>
            <Stack gap={2}>
              {features.length === 0 && (
                <Text size="xs" c="dimmed">
                  {t('map.noObjects')}
                </Text>
              )}
              {features.map((f) => (
                <Group
                  key={f.id}
                  gap={4}
                  wrap="nowrap"
                  onClick={() => handleSelectFeature(f.id)}
                  style={{
                    cursor: 'pointer',
                    borderRadius: 4,
                    padding: 4,
                    background: f.id === selectedFeatureId ? 'var(--mantine-color-blue-light)' : undefined,
                  }}
                >
                  <span style={{ color: FEATURE_COLORS[f.type], display: 'flex', flexShrink: 0 }}>{OBJECT_TYPE_ICONS[f.type]}</span>
                  <TextInput
                    size="xs"
                    variant="unstyled"
                    value={f.label ?? ''}
                    placeholder={t(`map.tools.${f.type}`)}
                    onChange={(e) => handleRenameFeature(f.id, e.currentTarget.value)}
                    onClick={(e) => e.stopPropagation()}
                    style={{ flex: 1, minWidth: 0 }}
                  />
                  <Tooltip label={t('map.focus')}>
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleFocusFeature(f)
                      }}
                    >
                      <IconCrosshair size={14} />
                    </ActionIcon>
                  </Tooltip>
                  {f.type === 'image' && (
                    <Tooltip label={t('map.calibrate')}>
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        color="teal"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleStartCalib(f.id)
                        }}
                      >
                        <IconRuler2 size={14} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                  <Tooltip label={t('common.delete')}>
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      color="red"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteFeature(f.id)
                      }}
                    >
                      <IconTrash size={14} />
                    </ActionIcon>
                  </Tooltip>
                </Group>
              ))}
            </Stack>
          </ScrollArea>
        </Paper>
      </Group>

      {calibState?.step === 1 && (() => {
        const imgUrl = features.find((f) => f.id === calibState.imageFeatureId)?.imageUrl
        return imgUrl ? (
          <ImageCalibModal
            imageUrl={imgUrl}
            points={calibState.imagePoints}
            onPointAdd={handleCalibImagePoint}
            onClose={() => setCalibState(null)}
          />
        ) : null
      })()}

      <Modal opened={saveModalOpened} onClose={closeSaveModal} title={t('map.saveAsTemplate')}>
        <form onSubmit={saveForm.onSubmit((values) => createMutation.mutate(values))}>
          <Stack gap="sm">
            <TextInput label={t('map.templateName')} required {...saveForm.getInputProps('name')} />
            <Textarea label={t('map.templateDescription')} {...saveForm.getInputProps('description')} />
            <Button type="submit" loading={createMutation.isPending}>
              {t('map.save')}
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  )
}
