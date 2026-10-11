/**
 * Página principal — lista de alertas de segurança.
 *
 * Server Component: busca alertas diretamente no servidor (SSR).
 * Renderiza lista vazia sem crash quando a API retorna [].
 */

import { fetchAlerts, fetchHealth } from '@/lib/api'
import type { Alert } from '@/lib/types'
import { AlertCard } from '@/components/AlertCard'
import { StatusBadge } from '@/components/StatusBadge'

export const dynamic = 'force-dynamic'  // sem cache — alertas mudam frequentemente

async function getPageData() {
  try {
    const [alerts, health] = await Promise.allSettled([fetchAlerts(), fetchHealth()])
    return {
      alerts: alerts.status === 'fulfilled' ? alerts.value : [],
      apiOnline: health.status === 'fulfilled' && health.value.status === 'ok',
      error: alerts.status === 'rejected' ? String(alerts.reason) : null,
    }
  } catch {
    return { alerts: [], apiOnline: false, error: 'Não foi possível conectar à API.' }
  }
}

export default async function HomePage() {
  const { alerts, apiOnline, error } = await getPageData()

  return (
    <div className="space-y-6">
      {/* ── Cabeçalho da página ───────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-sentinel-text">Alertas de Segurança</h1>
          <p className="text-sm text-sentinel-muted mt-0.5">
            Detecções por regras e modelo ML · Score não é probabilidade calibrada
          </p>
        </div>
        <StatusBadge online={apiOnline} />
      </div>

      {/* ── Erro de conexão ───────────────────────────────────────────── */}
      {error && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 text-sm text-orange-800">
          <strong>Aviso:</strong> {error}
          <span className="block mt-1 text-orange-600">
            Inicie a API com: <code className="font-mono bg-orange-100 px-1 rounded">uvicorn api.index:app --reload</code>
          </span>
        </div>
      )}

      {/* ── Lista de alertas ──────────────────────────────────────────── */}
      {alerts.length === 0 && !error ? (
        <EmptyState />
      ) : (
        <div className="space-y-3">
          {alerts.map((alert: Alert) => (
            <AlertCard key={alert.alert_id} alert={alert} />
          ))}
        </div>
      )}

      {/* ── Rodapé informativo ────────────────────────────────────────── */}
      {alerts.length > 0 && (
        <p className="text-xs text-sentinel-muted text-right">
          {alerts.length} alerta{alerts.length !== 1 ? 's' : ''} na sessão atual ·{' '}
          <span className="italic">alertas não persistem entre reinicializações da API</span>
        </p>
      )}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="sentinel-card text-center py-12 space-y-3">
      <div className="text-4xl text-sentinel-muted">✓</div>
      <h2 className="font-semibold text-sentinel-text">Nenhum alerta na sessão atual</h2>
      <p className="text-sm text-sentinel-muted max-w-md mx-auto">
        Envie eventos para <code className="font-mono bg-sentinel-surface px-1 rounded">POST /detect</code> para
        gerar alertas. Use os dados sintéticos como ponto de partida:
      </p>
      <pre className="text-xs bg-sentinel-surface border border-sentinel-border rounded p-3 text-left max-w-md mx-auto overflow-x-auto">
        {`python scripts/generate_synthetic_data.py
python scripts/validate_data.py --input data/synthetic/events.jsonl`}
      </pre>
    </div>
  )
}
