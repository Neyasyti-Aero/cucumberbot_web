import { Stack } from '@mantine/core'
import { MapEditor } from '@features/map-editor/ui/MapEditor'

export function MapEditorPage() {
  return (
    <Stack h="calc(100vh - 80px)" gap={0}>
      <MapEditor />
    </Stack>
  )
}
