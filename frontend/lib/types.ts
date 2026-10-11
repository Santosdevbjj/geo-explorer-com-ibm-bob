/**
 * Tipos TypeScript que espelham os schemas Pydantic da API Sentinel.
 * Fonte: src/sentinel/schemas.py
 */

// ── Enumerações ────────────────────────────────────────────────────────────

export type AlertCategory =
  | 'brute_force'
  | 'traffic_spike'
  | 'injection_attempt'
  | 'anomaly'
  | 'unknown'

export type AlertPriority = 'low' | 'medium' | 'high' | 'critical'

export type SignalSource = 'rule' | 'model'

// ── Modelos ────────────────────────────────────────────────────────────────

export interface Signal {
  name: string
  source: SignalSource
  value: number
  threshold: number
  /** Contribuição relativa deste sinal para o score final (0–1). */
  contribution: number
}

export interface Alert {
  alert_id: string
  created_at: string   // ISO 8601 UTC
  category: AlertCategory
  priority: AlertPriority
  /**
   * Score composto (0–1).
   * NÃO é uma probabilidade calibrada — ver campo `limitations`.
   */
  score: number
  signals: Signal[]
  source_event_ids: string[]
  limitations: string
  model_version: string
}

export interface ValidationReport {
  total_records: number
  valid_records: number
  invalid_records: number
  duplicate_ids: string[]
  missing_fields_summary: Record<string, number>
  passed: boolean
}

export interface DetectResponse {
  alerts_generated: number
  alerts: Alert[]
  validation_summary: {
    total: number
    valid: number
    invalid: number
    passed: boolean
  } | null
}

export interface HealthResponse {
  status: 'ok' | string
  service: string
  version: string
}

// ── Utilitários ────────────────────────────────────────────────────────────

/** Mapeamento de prioridade para classes Tailwind de cor. */
export const PRIORITY_COLORS: Record<AlertPriority, string> = {
  low: 'text-gray-600 bg-gray-100',
  medium: 'text-yellow-700 bg-yellow-100',
  high: 'text-orange-700 bg-orange-100',
  critical: 'text-red-700 bg-red-100',
}

/** Mapeamento de prioridade para rótulo em português. */
export const PRIORITY_LABELS: Record<AlertPriority, string> = {
  low: 'Baixa',
  medium: 'Média',
  high: 'Alta',
  critical: 'Crítica',
}

/** Mapeamento de categoria para rótulo em português. */
export const CATEGORY_LABELS: Record<AlertCategory, string> = {
  brute_force: 'Força Bruta',
  traffic_spike: 'Pico de Tráfego',
  injection_attempt: 'Tentativa de Injeção',
  anomaly: 'Anomalia',
  unknown: 'Desconhecida',
}
