import type { ForwardRefExoticComponent, RefAttributes } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import L from 'leaflet'
import { IconQrcode, IconHome, IconArrowsMove, IconMapPin } from '@tabler/icons-react'

type SimpleIcon = ForwardRefExoticComponent<
  { size?: string | number; color?: string; stroke?: string | number } & RefAttributes<SVGSVGElement>
>

export function createDivIcon(IconComponent: SimpleIcon, color: string): L.DivIcon {
  const html = renderToStaticMarkup(
    <div
      style={{
        background: color,
        width: 28,
        height: 28,
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        border: '2px solid white',
        boxShadow: '0 1px 4px rgba(0,0,0,0.4)',
      }}
    >
      <IconComponent size={16} color="white" stroke={2} />
    </div>,
  )
  return L.divIcon({ html, className: '', iconSize: [28, 28], iconAnchor: [14, 14] })
}

export const qrIcon = createDivIcon(IconQrcode, '#0ca678')
export const baseIcon = createDivIcon(IconHome, '#fd7e14')
export const waypointIcon = createDivIcon(IconMapPin, '#7048e8')

export function vertexIcon(isEndpoint: boolean, draggable: boolean): L.DivIcon {
  const size = isEndpoint ? 12 : 8
  const total = size + 6
  const half = total / 2
  return L.divIcon({
    html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${
      isEndpoint ? '#ffffff' : '#ced4da'
    };border:2px solid ${isEndpoint ? '#1971c2' : '#868e96'};cursor:${draggable ? 'move' : 'default'};box-shadow:0 0 2px rgba(0,0,0,0.5);"></div>`,
    className: '',
    iconSize: [total, total],
    iconAnchor: [half, half],
  })
}

export function dimensionLabel(text: string): L.DivIcon {
  return L.divIcon({
    html: `<div style="position:absolute;transform:translate(-50%,-50%);font-size:11px;background:rgba(0,0,0,0.65);color:#fff;padding:1px 5px;border-radius:3px;white-space:nowrap;font-weight:500;">${text}</div>`,
    className: '',
    iconSize: [0, 0],
  })
}

export const moveIcon = (() => {
  const html = renderToStaticMarkup(
    <div
      style={{
        background: '#1971c2',
        width: 28,
        height: 28,
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        border: '2px solid white',
        boxShadow: '0 1px 4px rgba(0,0,0,0.4)',
        cursor: 'move',
      }}
    >
      <IconArrowsMove size={16} color="white" stroke={2} />
    </div>,
  )
  return L.divIcon({ html, className: '', iconSize: [28, 28], iconAnchor: [14, 14] })
})()

export function calibPointIcon(n: 1 | 2): L.DivIcon {
  const bg = n === 1 ? '#f03e3e' : '#1971c2'
  return L.divIcon({
    html: `<div style="width:24px;height:24px;border-radius:50%;background:${bg};border:2px solid white;display:flex;align-items:center;justify-content:center;color:white;font-size:12px;font-weight:bold;box-shadow:0 1px 4px rgba(0,0,0,0.5);">${n}</div>`,
    className: '',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  })
}

export function axisLabel(text: string): L.DivIcon {
  return L.divIcon({
    html: `<div style="font-size:10px;color:#868e96;white-space:nowrap;">${text}</div>`,
    className: '',
    iconSize: [30, 14],
    iconAnchor: [-2, 7],
  })
}
