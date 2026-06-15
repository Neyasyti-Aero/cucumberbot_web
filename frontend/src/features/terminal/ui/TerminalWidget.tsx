import { Badge, Card, Group, Stack, Text } from '@mantine/core'
import { useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useTerminal } from '../model/useTerminal'

export function TerminalWidget() {
  const { t } = useTranslation()
  const containerRef = useRef<HTMLDivElement>(null)
  const { connected } = useTerminal(containerRef)

  return (
    <Stack h="100%" gap="sm">
      <Group justify="space-between">
        <Text fw={600} size="lg">
          {t('terminal.title')}
        </Text>
        <Badge color={connected ? 'green' : 'red'} variant="dot">
          {connected ? t('terminal.connected') : t('terminal.disconnected')}
        </Badge>
      </Group>
      <Card
        withBorder
        p={0}
        style={{ flex: 1, overflow: 'hidden', background: '#0d1117', minHeight: 400 }}
      >
        <div ref={containerRef} style={{ height: '100%', width: '100%' }} />
      </Card>
    </Stack>
  )
}
