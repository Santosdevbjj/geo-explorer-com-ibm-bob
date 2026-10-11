/**
 * Página de métricas e model card do Sentinel.
 *
 * Exibe o último relatório de avaliação do modelo e informações
 * sobre as limitações do score de detecção.
 */

import { fetchMetrics } from '@/lib/api'

export const dynamic = 'force-dynamic'

async function getMetrics() {
  try {
    const data = await fetchMetrics()
    return { data, error: null }
  } catch (err) {
    return { data: null, error: String(err) }
  }
}

export default async function MetricsPage() {
  const { data, error } = await getMetrics()

  return (
    <div className="space-y-6">
      {/* ── Cabeçalho ─────────────────────────────────────────────────── */}
      <div>
        <h1 className="text-xl font-bold text-sentinel-text">Métricas do Modelo</h1>
        <p className="text-sm text-sentinel-muted mt-0.5">
          Avaliação sobre dados sintéticos · Não representa desempenho em dados reais
        </p>
      </div>

      {/* ── Aviso proeminente sobre limitações ────────────────────────── */}
      <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 text-sm text-orange-900 space-y-1">
        <p className="font-semibold">⚠️ Sobre as métricas</p>
        <p>
          Os valores abaixo foram calculados sobre <strong>dados sintéticos com rótulos simulados</strong>.
          Eles servem apenas para comparação entre versões do modelo —
          não representam desempenho em dados reais de produção.
        </p>
        <p>
          O <strong>score de anomalia</strong> não é uma probabilidade calibrada.
          Não o interprete como &ldquo;X% de chance de ser um ataque&rdquo;.
        </p>
      </div>

      {/* ── Erro de conexão ───────────────────────────────────────────── */}
      {error && (
        <div className="sentinel-card bg-red-50 border-red-200 text-sm text-red-800">
          Erro ao buscar métricas: {error}
        </div>
      )}

      {/* ── Status do modelo ──────────────────────────────────────────── */}
      {data && (
        <div className="sentinel-card space-y-2">
          <h2 className="font-semibold text-sentinel-text text-sm">Status do Modelo</h2>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <MetaItem
              label="Versão"
              value={String(data.model_version ?? '—')}
            />
            <MetaItem
              label="Modelo carregado"
              value={data.model_loaded ? '✅ Sim' : '⚠️ Não (modo rules-only)'}
            />
          </div>
        </div>
      )}

      {/* ── Relatório de avaliação ────────────────────────────────────── */}
      {data?.evaluation && typeof data.evaluation === 'object' && (
        <EvaluationBlock evaluation={data.evaluation as Record<string, unknown>} />
      )}

      {/* ── Link para model-card ──────────────────────────────────────── */}
      <div className="sentinel-card bg-sentinel-surface text-sm text-sentinel-muted space-y-1">
        <p className="font-medium text-sentinel-text">Documentação completa</p>
        <p>
          O model-card com limitações detalhadas, features e decisões de design está em{' '}
          <code className="font-mono bg-white border border-sentinel-border rounded px-1">
            docs/model-card.md
          </code>{' '}
          no repositório.
        </p>
        <a
          href="https://github.com/Santosdevbjj/geo-explorer-com-ibm-bob/blob/main/docs/model-card.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-sentinel-accent hover:underline"
        >
          Ver model-card no GitHub ↗
        </a>
      </div>
    </div>
  )
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-sentinel-muted">{label}</p>
      <p className="font-medium text-sentinel-text">{value}</p>
    </div>
  )
}

function EvaluationBlock({ evaluation }: { evaluation: Record<string, unknown> }) {
  // Caso sem relatório disponível
  if ('message' in evaluation) {
    return (
      <div className="sentinel-card text-sm text-sentinel-muted space-y-1">
        <p className="font-medium text-sentinel-text">Relatório de Avaliação</p>
        <p>{String(evaluation.message)}</p>
        <p className="text-xs">
          Execute:{' '}
          <code className="font-mono bg-sentinel-surface border border-sentinel-border rounded px-1">
            python scripts/evaluate_model.py
          </code>
        </p>
      </div>
    )
  }

  const results = (evaluation.results as Array<Record<string, unknown>> | undefined) ?? []

  return (
    <div className="space-y-3">
      <h2 className="font-semibold text-sentinel-text text-sm">Relatório de Avaliação</h2>
      {results.length === 0 ? (
        <p className="text-sm text-sentinel-muted">Nenhum resultado disponível.</p>
      ) : (
        results.map((r, i) => (
          <div key={i} className="sentinel-card space-y-3">
            <p className="font-medium text-sentinel-text text-sm">
              Detector: <code className="font-mono text-sentinel-accent">{String(r.detector)}</code>
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <MetricValue label="Precision" value={r.precision} />
              <MetricValue label="Recall" value={r.recall} />
              <MetricValue label="F1" value={r.f1} />
              <MetricValue label="FPR" value={r.false_positive_rate} />
            </div>
            <div className="grid grid-cols-4 gap-2 text-xs text-center pt-2 border-t border-sentinel-border">
              {(['tp', 'fp', 'fn', 'tn'] as const).map((key) => (
                <div key={key} className="bg-sentinel-surface rounded p-1.5">
                  <div className="font-bold text-sentinel-text">{String(r[key] ?? '—')}</div>
                  <div className="text-sentinel-muted uppercase">{key}</div>
                </div>
              ))}
            </div>
          </div>
        ))
      )}
      {evaluation.disclaimer && (
        <p className="text-xs text-sentinel-muted italic">{String(evaluation.disclaimer)}</p>
      )}
    </div>
  )
}

function MetricValue({ label, value }: { label: string; value: unknown }) {
  const display = value === null || value === undefined ? '—' : String(value)
  return (
    <div>
      <p className="text-xs text-sentinel-muted">{label}</p>
      <p className="font-bold text-sentinel-text">{display}</p>
    </div>
  )
}
