import { Badge, Card, Group, Progress, SimpleGrid, Stack, Text } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { AreaChart } from '@mantine/charts'
import { useRef, useState } from 'react'
import { useRobotStatus } from '../model/useTelemetry'

const MAX_HISTORY = 60

export function TelemetryWidget() {
  const { t } = useTranslation()
  const { telemetry, connectionStatus } = useRobotStatus()
  const [history, setHistory] = useState<{ time: number; x: number; y: number }[]>([])
  const prevTimestamp = useRef(0)

  if (telemetry.timestamp !== prevTimestamp.current && telemetry.timestamp > 0) {
    prevTimestamp.current = telemetry.timestamp
    setHistory((prev) => [
      ...prev.slice(-MAX_HISTORY + 1),
      { time: Date.now(), x: telemetry.x, y: telemetry.y },
    ])
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Text fw={600} size="lg">
          {t('telemetry.title')}
        </Text>
        <Badge color={connectionStatus === 'connected' ? 'green' : 'red'} variant="dot">
          {connectionStatus === 'connected' ? t('telemetry.connected') : t('telemetry.disconnected')}
        </Badge>
      </Group>

      <SimpleGrid cols={3}>
        <Card withBorder padding="sm">
          <Text size="xs" c="dimmed">
            {t('telemetry.x')}
          </Text>
          <Text fw={700} size="xl">
            {telemetry.x.toFixed(3)}
          </Text>
        </Card>
        <Card withBorder padding="sm">
          <Text size="xs" c="dimmed">
            {t('telemetry.y')}
          </Text>
          <Text fw={700} size="xl">
            {telemetry.y.toFixed(3)}
          </Text>
        </Card>
        <Card withBorder padding="sm">
          <Text size="xs" c="dimmed">
            {t('telemetry.theta')}
          </Text>
          <Text fw={700} size="xl">
            {((telemetry.theta * 180) / Math.PI).toFixed(1)}°
          </Text>
        </Card>
      </SimpleGrid>

      <Card withBorder padding="sm">
        <Group justify="space-between" mb="xs">
          <Text size="sm">{t('telemetry.battery')}</Text>
          <Text size="sm" fw={600}>
            {telemetry.battery_percent.toFixed(0)}%
          </Text>
        </Group>
        <Progress
          value={telemetry.battery_percent}
          color={telemetry.battery_percent < 20 ? 'red' : telemetry.battery_percent < 50 ? 'yellow' : 'green'}
          size="lg"
        />
      </Card>

      <Card withBorder padding="sm">
        <Text size="sm" mb="xs">
          {t('telemetry.taskStatus')}:{' '}
          <Badge variant="light">{telemetry.task_status}</Badge>
        </Text>
      </Card>

      {history.length > 1 && (
        <Card withBorder padding="sm">
          <Text size="sm" mb="xs">
            Траектория X/Y
          </Text>
          <AreaChart
            h={120}
            data={history}
            dataKey="time"
            series={[
              { name: 'x', color: 'green.6' },
              { name: 'y', color: 'blue.6' },
            ]}
            withDots={false}
          />
        </Card>
      )}
    </Stack>
  )
}
