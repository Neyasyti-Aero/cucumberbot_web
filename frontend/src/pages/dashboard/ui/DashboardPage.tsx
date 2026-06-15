import { Grid, Stack } from '@mantine/core'
import { RobotControlPanel } from '@features/robot-control/ui/RobotControlPanel'
import { TelemetryWidget } from '@features/telemetry-stream/ui/TelemetryWidget'

export function DashboardPage() {
  return (
    <Grid gutter="md" h="100%">
      <Grid.Col span={{ base: 12, md: 8 }}>
        <Stack gap="md">
          <RobotControlPanel />
        </Stack>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 4 }}>
        <TelemetryWidget />
      </Grid.Col>
    </Grid>
  )
}
