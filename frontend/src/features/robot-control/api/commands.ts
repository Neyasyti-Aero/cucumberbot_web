import { api } from '@shared/api/base'
import type { CommandType } from '@entities/robot/model/types'

export async function sendCommand(command: CommandType, payload: Record<string, unknown> = {}) {
  const { data } = await api.post('/robot/command', { command, payload })
  return data
}
