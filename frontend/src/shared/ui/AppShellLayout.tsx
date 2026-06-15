import { AppShell, Badge, Burger, Group, NavLink, Text } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useTranslation } from 'react-i18next'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  IconLayoutDashboard,
  IconMap,
  IconTerminal2,
  IconUsers,
  IconLogout,
} from '@tabler/icons-react'
import { useTelemetry, useRobotStatus } from '@features/telemetry-stream/model/useTelemetry'

const navItems = [
  { href: '/dashboard', icon: IconLayoutDashboard, key: 'nav.dashboard' },
  { href: '/map-editor', icon: IconMap, key: 'nav.mapEditor' },
  { href: '/terminal', icon: IconTerminal2, key: 'nav.terminal' },
  { href: '/admin', icon: IconUsers, key: 'nav.admin' },
]

export function AppShellLayout() {
  const [opened, { toggle }] = useDisclosure()
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  useTelemetry()
  const { robotConnected } = useRobotStatus()

  const handleLogout = () => {
    localStorage.clear()
    navigate('/login')
  }

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 240, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Text fw={700} size="lg" c="green">
              🥒 CucumberBot
            </Text>
          </Group>
          <Badge color={robotConnected ? 'green' : 'gray'} variant="dot" size="lg">
            {robotConnected ? t('status.robotConnected') : `${t('status.robotDisconnected')} — ${t('status.testMode')}`}
          </Badge>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="sm">
        {navItems.map(({ href, icon: Icon, key }) => (
          <NavLink
            key={href}
            label={t(key)}
            leftSection={<Icon size={18} />}
            active={location.pathname === href}
            onClick={() => navigate(href)}
            mb={4}
          />
        ))}
        <NavLink
          label={t('nav.logout')}
          leftSection={<IconLogout size={18} />}
          onClick={handleLogout}
          color="red"
          mt="auto"
        />
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  )
}
