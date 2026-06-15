export interface Telemetry {
  x: number
  y: number
  theta: number
  battery_percent: number
  task_status: string
  timestamp: number
}

export type CommandType = 'patrol' | 'collect' | 'return_to_base' | 'stop' | 'move_to'

export interface RobotCommand {
  command: CommandType
  payload?: Record<string, unknown>
}

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected'
