/**
 * AlertCard — card resumido de alerta para a lista principal.
 */

import Link from 'next/link'
import type { Alert } from '@/lib/types'
import { PriorityBadge } from './PriorityBadge'
import { CategoryBadge } from './CategoryBadge'

interface Props {
  alert: Alert
}

export function AlertCard({ alert }: Props) {
  const createdAt = new Date(alert.created_at).toLocaleString('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: 'America/Sao_Paulo',
  })

  const topSignal = alert.signals.length > 0
    ? alert.signals.reduce((a, b) => a.contribution > b.contribution ? a : b)
    : null

  return (
    <Link
      href={`/alerts/${alert.alert_id}`}
      className="block sentinel-card hover:border-sentinel-accent transition-colors group"
    >
      <div className="flex items-start justify-between gap-4">
        {/* Coluna esquerda: categoria + sinal principal */}
        <div className="min-w-0 space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <CategoryBadge category={alert.category} />
            <PriorityBadge priority={alert.priority} />
          </div>
          {topSignal && (
            <p className="text-xs text-sentinel-muted">
              Sinal principal:{' '}
              <span className="font-medium text-sentinel-text">{topSignal.name}</span>
              {' '}({topSignal.source}) · contribuição{' '}
              {(topSignal.contribution * 100).toFixed(0)}%
            </p>
          )}
          <p className="text-xs font-mono text-sentinel-muted truncate">{alert.alert_id}</p>
        </div>

        {/* Coluna direita: score + data */}
        <div className="shrink-0 text-right space-y-1">
          <div className="text-base font-bold text-sentinel-text">
            {alert.score.toFixed(2)}
          </div>
          <p className="text-xs text-sentinel-muted">score</p>
          <p className="text-xs text-sentinel-muted">{createdAt}</p>
        </div>
      </div>

      {/* Indicador de "ver detalhes" */}
      <p className="text-xs text-sentinel-accent mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
        Ver sinais e limitações →
      </p>
    </Link>
  )
}
