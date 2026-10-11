/**
 * PriorityBadge — badge de nível de prioridade com cor semântica.
 */

import type { AlertPriority } from '@/lib/types'
import { PRIORITY_COLORS, PRIORITY_LABELS } from '@/lib/types'

interface Props {
  priority: AlertPriority
}

export function PriorityBadge({ priority }: Props) {
  return (
    <span className={`sentinel-badge ${PRIORITY_COLORS[priority]}`}>
      {PRIORITY_LABELS[priority]}
    </span>
  )
}
