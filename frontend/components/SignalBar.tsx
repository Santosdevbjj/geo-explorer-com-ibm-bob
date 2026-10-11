/**
 * SignalBar — visualização de um sinal de detecção com barra de contribuição.
 */

import type { Signal } from '@/lib/types'

interface Props {
  signal: Signal
}

export function SignalBar({ signal }: Props) {
  const pct = Math.round(signal.contribution * 100)
  const sourceColor = signal.source === 'rule'
    ? 'bg-sentinel-accent'
    : 'bg-sentinel-purple'

  return (
    <div className="sentinel-card space-y-2">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-sentinel-text truncate">{signal.name}</p>
          <p className="text-xs text-sentinel-muted">
            Origem:{' '}
            <span className="font-medium">{signal.source === 'rule' ? 'Regra' : 'Modelo ML'}</span>
            {' · '}Valor: <span className="font-mono">{signal.value.toFixed(0)}</span>
            {' · '}Limiar: <span className="font-mono">{signal.threshold.toFixed(0)}</span>
          </p>
        </div>
        <div className="shrink-0 text-right">
          <span className="text-sm font-bold text-sentinel-text">{pct}%</span>
          <p className="text-xs text-sentinel-muted">contribuição</p>
        </div>
      </div>

      {/* Barra de progresso */}
      <div className="h-1.5 bg-sentinel-surface rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${sourceColor} transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
