import { create } from 'zustand'
import type { ConnectionStatus, Telemetry } from './types'

interface RobotStore {
  telemetry: Telemetry
  connectionStatus: ConnectionStatus
  robotConnected: boolean
  setTelemetry: (t: Telemetry) => void
  setConnectionStatus: (s: ConnectionStatus) => void
  setRobotConnected: (connected: boolean) => void
}

export const useRobotStore = create<RobotStore>((set) => ({
  telemetry: { x: 0, y: 0, theta: 0, battery_percent: 0, task_status: 'idle', timestamp: 0 },
  connectionStatus: 'disconnected',
  robotConnected: false,
  setTelemetry: (telemetry) => set({ telemetry }),
  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
  setRobotConnected: (robotConnected) => set({ robotConnected }),
}))
