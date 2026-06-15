import { Stack } from '@mantine/core'
import { TerminalWidget } from '@features/terminal/ui/TerminalWidget'

export function TerminalPage() {
  return (
    <Stack h="calc(100vh - 80px)" gap={0}>
      <TerminalWidget />
    </Stack>
  )
}
