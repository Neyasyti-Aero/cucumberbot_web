import { MantineProvider, createTheme } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'

import { DashboardPage } from '@pages/dashboard'
import { MapEditorPage } from '@pages/map-editor'
import { TerminalPage } from '@pages/terminal'
import { AdminPage } from '@pages/admin'
import { LoginPage } from '@pages/login'
import { ProtectedRoute } from '@shared/ui/ProtectedRoute'
import { AppShellLayout } from '@shared/ui/AppShellLayout'

const theme = createTheme({
  primaryColor: 'green',
  fontFamily: 'Inter, sans-serif',
})

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <MantineProvider theme={theme} defaultColorScheme="dark">
        <Notifications position="top-right" />
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<AppShellLayout />}>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/map-editor" element={<MapEditorPage />} />
                <Route path="/terminal" element={<TerminalPage />} />
                <Route path="/admin" element={<AdminPage />} />
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </MantineProvider>
    </QueryClientProvider>
  )
}
