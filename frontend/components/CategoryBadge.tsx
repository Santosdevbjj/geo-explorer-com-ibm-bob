/**
 * CategoryBadge — badge de categoria de alerta.
 */

import type { AlertCategory } from '@/lib/types'
import { CATEGORY_LABELS } from '@/lib/types'

interface Props {
  category: AlertCategory
}

const CATEGORY_COLORS: Record<AlertCategory, string> = {
  brute_force: 'text-red-700 bg-red-50 border border-red-200',
  traffic_spike: 'text-orange-700 bg-orange-50 border border-orange-200',
  injection_attempt: 'text-purple-700 bg-purple-50 border border-purple-200',
  anomaly: 'text-blue-700 bg-blue-50 border border-blue-200',
  unknown: 'text-gray-600 bg-gray-100 border border-gray-200',
}

export function CategoryBadge({ category }: Props) {
  return (
    <span className={`sentinel-badge ${CATEGORY_COLORS[category]}`}>
      {CATEGORY_LABELS[category]}
    </span>
  )
}
