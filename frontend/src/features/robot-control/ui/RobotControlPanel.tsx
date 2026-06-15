import { Button, Group, Stack, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { IconPlayerPlay, IconPackage, IconHome, IconPlayerStop } from '@tabler/icons-react'
import { sendCommand } from '../api/commands'
import type { CommandType } from '@entities/robot/model/types'

const COMMANDS: { key: CommandType; icon: React.ReactNode; color: string }[] = [
  { key: 'patrol', icon: <IconPlayerPlay size={18} />, color: 'green' },
  { key: 'collect', icon: <IconPackage size={18} />, color: 'blue' },
  { key: 'return_to_base', icon: <IconHome size={18} />, color: 'orange' },
  { key: 'stop', icon: <IconPlayerStop size={18} />, color: 'red' },
]

export function RobotControlPanel() {
  const { t } = useTranslation()

  const { mutate, isPending } = useMutation({
    mutationFn: (cmd: CommandType) => sendCommand(cmd),
    onSuccess: (_data, cmd) => {
      notifications.show({ title: t('robot.commandSent'), message: t(`robot.${cmd}`), color: 'green' })
    },
    onError: () => {
      notifications.show({ title: t('robot.commandError'), message: '', color: 'red' })
    },
  })

  return (
    <Stack gap="sm">
      <Text fw={600} size="lg">
        Управление роботом
      </Text>
      <Group>
        {COMMANDS.map(({ key, icon, color }) => (
          <Button
            key={key}
            leftSection={icon}
            color={color}
            variant={key === 'stop' ? 'filled' : 'light'}
            loading={isPending}
            onClick={() => mutate(key)}
            size="lg"
          >
            {t(`robot.${key === 'return_to_base' ? 'returnToBase' : key}`)}
          </Button>
        ))}
      </Group>
    </Stack>
  )
}
