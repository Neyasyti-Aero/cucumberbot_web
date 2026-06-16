import { Modal, Stack, Text } from '@mantine/core'
import { useTranslation } from 'react-i18next'

interface Props {
  imageUrl: string
  points: [number, number][]
  onPointAdd: (frac: [number, number]) => void
  onClose: () => void
}

const POINT_COLORS = ['#f03e3e', '#1971c2']

export function ImageCalibModal({ imageUrl, points, onPointAdd, onClose }: Props) {
  const { t } = useTranslation()

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (points.length >= 2) return
    const rect = e.currentTarget.getBoundingClientRect()
    onPointAdd([(e.clientX - rect.left) / rect.width, (e.clientY - rect.top) / rect.height])
  }

  const instructions: string[] = [t('map.calibClickImage1'), t('map.calibClickImage2'), t('map.calibDoneImage')]

  return (
    <Modal opened onClose={onClose} title={t('map.calibTitle')} size="lg">
      <Stack gap="xs">
        <Text size="sm" c={points.length < 2 ? undefined : 'teal'}>
          {instructions[Math.min(points.length, 2)]}
        </Text>
        <div
          onClick={handleClick}
          style={{ position: 'relative', cursor: points.length < 2 ? 'crosshair' : 'default', lineHeight: 0 }}
        >
          <img src={imageUrl} alt="" style={{ width: '100%', display: 'block', userSelect: 'none' }} draggable={false} />
          {points.map(([fx, fy], i) => (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: `${fx * 100}%`,
                top: `${fy * 100}%`,
                transform: 'translate(-50%, -50%)',
                width: 24,
                height: 24,
                borderRadius: '50%',
                background: POINT_COLORS[i],
                border: '2px solid white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                fontSize: 12,
                fontWeight: 'bold',
                pointerEvents: 'none',
                boxShadow: '0 1px 4px rgba(0,0,0,0.5)',
              }}
            >
              {i + 1}
            </div>
          ))}
        </div>
      </Stack>
    </Modal>
  )
}
