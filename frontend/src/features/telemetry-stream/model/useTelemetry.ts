import { useEffect, useRef } from 'react'
import { useRobotStore } from '@entities/robot/model/store'
import type { Telemetry } from '@entities/robot/model/types'

export function useTelemetry() {
  const wsRef = useRef<WebSocket | null>(null)
  const { setTelemetry, setConnectionStatus, setRobotConnected } = useRobotStore()

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/api/v1/robot/ws/telemetry?token=${token}`)
    wsRef.current = ws

    setConnectionStatus('connecting')

    ws.onopen = () => setConnectionStatus('connected')

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (typeof data.robot_connected === 'boolean') {
          setRobotConnected(data.robot_connected)
        }
        if ('ping' in data) return
        setTelemetry(data as Telemetry)
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = () => {
      setConnectionStatus('disconnected')
      setRobotConnected(false)
    }
    ws.onerror = () => {
      setConnectionStatus('disconnected')
      setRobotConnected(false)
    }

    return () => {
      ws.close()
    }
  }, [setTelemetry, setConnectionStatus, setRobotConnected])
}

export function useRobotStatus() {
  const telemetry = useRobotStore((s) => s.telemetry)
  const connectionStatus = useRobotStore((s) => s.connectionStatus)
  const robotConnected = useRobotStore((s) => s.robotConnected)
  return { telemetry, connectionStatus, robotConnected }
}
