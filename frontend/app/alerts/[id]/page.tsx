/**
 * Página de detalhe de alerta.
 *
 * Server Component: busca o alerta pelo ID da URL.
 * Exibe sinais de detecção e limitações explícitas da avaliação.
 */

import { notFound } from 'next/navigation'
import Link from 'next/link'
import { fetchAlert } from '@/lib/api'
import { PriorityBadge } from '@/components/PriorityBadge'
import { CategoryBadge } from '@/components/CategoryBadge'
import { SignalBar } from '@/components/SignalBar'
import { CATEGORY_LABELS } from '@/lib/types'

interface Props {
  params: { id: string }
}

export default async function AlertDetailPage({ params }: Props) {
  const alert = await fetchAlert(params.id)

  if (!alert) {
    notFound()
  }

  const createdAt = new Date(alert.created_at).toLocaleString('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'medium',
    timeZone: 'America/Sao_Paulo',
  })

  return (
    <div className="space-y-6">
      {/* ── Navegação ─────────────────────────────────────────────────── */}
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-sm text-sentinel-muted hover:text-sentinel-text transition-colors"
      >
        ← Voltar para alertas
      </Link>

      {/* ── Cabeçalho do alerta ───────────────────────────────────────── */}
      <div className="sentinel-card space-y-3">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-base font-bold text-sentinel-text">
              {CATEGORY_LABELS[alert.category]}
            </h1>
            <p className="text-xs text-sentinel-muted font-mono">{alert.alert_id}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <CategoryBadge category={alert.category} />
            <PriorityBadge priority={alert.priority} />
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 border-t border-sentinel-border">
          <MetaItem label="Score" value={alert.score.toFixed(4)} />
          <MetaItem label="Modelo" value={alert.model_version} />
          <MetaItem label="Gerado em" value={createdAt} />
          <MetaItem label="Eventos origem" value={String(alert.source_event_ids.length)} />
        </div>

        {/* Aviso explícito sobre o score */}
        <p className="text-xs text-sentinel-muted italic border-t border-sentinel-border pt-2">
          ⚠️ Score não é probabilidade calibrada — veja Limitações abaixo.
        </p>
      </div>

      {/* ── Sinais de detecção ────────────────────────────────────────── */}
      <section className="space-y-3">
        <h2 className="font-semibold text-sentinel-text text-sm">
          Sinais de Detecção ({alert.signals.length})
        </h2>
        {alert.signals.length === 0 ? (
          <p className="text-sm text-sentinel-muted">Nenhum sinal disponível.</p>
        ) : (
          <div className="space-y-2">
            {alert.signals.map((signal, i) => (
              <SignalBar key={i} signal={signal} />
            ))}
          </div>
        )}
      </section>

      {/* ── Limitações da avaliação ───────────────────────────────────── */}
      <section className="space-y-2">
        <h2 className="font-semibold text-sentinel-text text-sm">Limitações da Avaliação</h2>
        <div className="sentinel-card bg-orange-50 border-orange-200 text-sm text-orange-900">
          {alert.limitations}
        </div>
      </section>

      {/* ── IDs dos eventos de origem ─────────────────────────────────── */}
      {alert.source_event_ids.length > 0 && (
        <section className="space-y-2">
          <h2 className="font-semibold text-sentinel-text text-sm">
            Eventos de Origem ({alert.source_event_ids.length})
          </h2>
          <div className="sentinel-card overflow-x-auto">
            <div className="flex flex-wrap gap-1.5">
              {alert.source_event_ids.slice(0, 20).map((id) => (
                <code
                  key={id}
                  className="text-xs bg-sentinel-surface border border-sentinel-border rounded px-1.5 py-0.5 text-sentinel-muted font-mono"
                >
                  {id}
                </code>
              ))}
              {alert.source_event_ids.length > 20 && (
                <span className="text-xs text-sentinel-muted self-center">
                  +{alert.source_event_ids.length - 20} mais
                </span>
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  )
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-0.5">
      <p className="text-xs text-sentinel-muted">{label}</p>
      <p className="text-sm font-medium text-sentinel-text truncate">{value}</p>
    </div>
  )
}

export async function generateMetadata({ params }: Props) {
  const alert = await fetchAlert(params.id)
  if (!alert) return { title: 'Alerta não encontrado — Sentinel' }
  return {
    title: `Alerta ${CATEGORY_LABELS[alert.category]} — Sentinel`,
    description: `Prioridade ${alert.priority} · Score ${alert.score.toFixed(2)}`,
  }
}
