import { Button, Card, Center, PasswordInput, Stack, Text, TextInput, Title } from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { api } from '@shared/api/base'

interface LoginValues {
  email: string
  password: string
}

export function LoginForm() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const form = useForm<LoginValues>({
    initialValues: { email: '', password: '' },
    validate: {
      email: (v) => (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? null : 'Неверный формат email'),
      password: (v) => (v.length >= 6 ? null : 'Минимум 6 символов'),
    },
  })

  const { mutate, isPending } = useMutation({
    mutationFn: (values: LoginValues) => api.post('/auth/login', values).then((r) => r.data),
    onSuccess: (data) => {
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      navigate('/dashboard')
    },
    onError: () => {
      notifications.show({ title: t('auth.loginError'), message: '', color: 'red' })
    },
  })

  return (
    <Center h="100vh">
      <Card withBorder shadow="md" p="xl" w={400}>
        <Stack gap="md">
          <Stack gap={4} align="center">
            <Title order={2} c="green">
              🥒 {t('auth.title')}
            </Title>
            <Text size="sm" c="dimmed">
              {t('auth.subtitle')}
            </Text>
          </Stack>

          <form onSubmit={form.onSubmit((v) => mutate(v))}>
            <Stack gap="sm">
              <TextInput
                label={t('auth.email')}
                placeholder="admin@cucumberbot.io"
                {...form.getInputProps('email')}
              />
              <PasswordInput
                label={t('auth.password')}
                placeholder="••••••••"
                {...form.getInputProps('password')}
              />
              <Button type="submit" loading={isPending} fullWidth mt="sm">
                {t('auth.loginButton')}
              </Button>
            </Stack>
          </form>
        </Stack>
      </Card>
    </Center>
  )
}
