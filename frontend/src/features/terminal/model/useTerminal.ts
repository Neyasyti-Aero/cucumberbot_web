import { useEffect, useRef, useState } from 'react'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'

export function useTerminal(containerRef: React.RefObject<HTMLDivElement | null>) {
  const termRef = useRef<Terminal | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const [connected, setConnected] = useState(false)
  const inputBuffer = useRef('')

  useEffect(() => {
    if (!containerRef.current) return

    const term = new Terminal({
      theme: { background: '#0d1117', foreground: '#c9d1d9', cursor: '#58a6ff' },
      fontFamily: 'JetBrains Mono, Fira Code, monospace',
      fontSize: 13,
      cursorBlink: true,
    })

    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    term.open(containerRef.current)
    fitAddon.fit()

    termRef.current = term
    fitAddonRef.current = fitAddon

    const token = localStorage.getItem('access_token')
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/api/v1/terminal/ws?token=${token}`)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      term.writeln('\r\n\x1b[31mСоединение закрыто\x1b[0m')
    }
    ws.onmessage = (e) => term.write(e.data)

    term.onKey(({ key, domEvent }) => {
      if (domEvent.key === 'Enter') {
        ws.send(inputBuffer.current)
        term.writeln('')
        inputBuffer.current = ''
      } else if (domEvent.key === 'Backspace') {
        if (inputBuffer.current.length > 0) {
          inputBuffer.current = inputBuffer.current.slice(0, -1)
          term.write('\b \b')
        }
      } else {
        inputBuffer.current += key
        term.write(key)
      }
    })

    const handleResize = () => fitAddon.fit()
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      ws.close()
      term.dispose()
    }
  }, [containerRef])

  return { connected }
}
