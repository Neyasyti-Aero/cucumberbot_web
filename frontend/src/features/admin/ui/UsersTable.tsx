import {
  ActionIcon,
  Badge,
  Button,
  Group,
  Modal,
  PasswordInput,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { IconTrash } from '@tabler/icons-react'
import { api } from '@shared/api/base'

interface User {
  id: string
  email: string
  role: string
  is_active: boolean
}

function useUsers() {
  return useQuery<User[]>({ queryKey: ['users'], queryFn: () => api.get('/users/').then((r) => r.data) })
}

export function UsersTable() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const { data: users = [] } = useUsers()
  const [opened, { open, close }] = useDisclosure()

  const form = useForm({
    initialValues: { email: '', password: '', role: 'operator' },
    validate: {
      email: (v) => (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? null : 'Неверный email'),
      password: (v) => (v.length >= 6 ? null : 'Минимум 6 символов'),
    },
  })

  const createMutation = useMutation({
    mutationFn: (values: typeof form.values) => api.post('/users/', values).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      notifications.show({ title: t('common.success'), message: '', color: 'green' })
      close()
      form.reset()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/users/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })

  const rows = users.map((u) => (
    <Table.Tr key={u.id}>
      <Table.Td>{u.email}</Table.Td>
      <Table.Td>
        <Badge color={u.role === 'admin' ? 'red' : 'blue'} variant="light">
          {t(`admin.roles.${u.role}`)}
        </Badge>
      </Table.Td>
      <Table.Td>
        <Badge color={u.is_active ? 'green' : 'gray'} variant="dot">
          {u.is_active ? t('admin.active') : t('admin.inactive')}
        </Badge>
      </Table.Td>
      <Table.Td>
        <ActionIcon color="red" variant="light" onClick={() => deleteMutation.mutate(u.id)}>
          <IconTrash size={16} />
        </ActionIcon>
      </Table.Td>
    </Table.Tr>
  ))

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Text fw={600} size="lg">
          {t('admin.title')}
        </Text>
        <Button onClick={open} size="sm">
          {t('admin.addUser')}
        </Button>
      </Group>

      <Table striped highlightOnHover withTableBorder>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('admin.email')}</Table.Th>
            <Table.Th>{t('admin.role')}</Table.Th>
            <Table.Th>{t('admin.status')}</Table.Th>
            <Table.Th>{t('admin.actions')}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>{rows}</Table.Tbody>
      </Table>

      <Modal opened={opened} onClose={close} title={t('admin.addUser')}>
        <form onSubmit={form.onSubmit((v) => createMutation.mutate(v))}>
          <Stack gap="sm">
            <TextInput label={t('admin.email')} {...form.getInputProps('email')} />
            <PasswordInput label={t('auth.password')} {...form.getInputProps('password')} />
            <Select
              label={t('admin.role')}
              data={[
                { value: 'operator', label: t('admin.roles.operator') },
                { value: 'admin', label: t('admin.roles.admin') },
              ]}
              {...form.getInputProps('role')}
            />
            <Button type="submit" loading={createMutation.isPending}>
              {t('common.save')}
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  )
}
