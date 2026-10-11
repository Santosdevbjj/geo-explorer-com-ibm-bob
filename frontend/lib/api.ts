/**
 * Camada de acesso à API Sentinel.
 * URL base configurada via NEXT_PUBLIC_API_URL (ver next.config.js).
 */

import type { Alert, DetectResponse, HealthResponse, ValidationReport } from './types'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// Chave de API — em produção injete via variável de ambiente NEXT_PUBLIC_API_KEY
// NÃO comite chaves reais neste arquivo.
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? ''

// ── Headers padrão ─────────────────────────────────────────────────────────

function buildHeaders(withAuth = false): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (withAuth && API_KEY) {
    headers['X-Api-Key'] = API_KEY
  }
  return headers
}

// ── Funções de fetch tipadas ────────────────────────────────────────────────

/**
 * Verifica o status da API.
 * Endpoint público — não requer autenticação.
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/health`, {
    headers: buildHeaders(),
    next: { revalidate: 30 },  // cache de 30s no Next.js App Router
  })
  if (!res.ok) throw new Error(`/health retornou ${res.status}`)
  return res.json() as Promise<HealthResponse>
}

/**
 * Lista todos os alertas da sessão atual.
 * Endpoint público — não requer autenticação.
 */
export async function fetchAlerts(): Promise<Alert[]> {
  const res = await fetch(`${API_URL}/alerts`, {
    headers: buildHeaders(),
    cache: 'no-store',  // alertas mudam a cada chamada de /detect
  })
  if (!res.ok) throw new Error(`/alerts retornou ${res.status}`)
  return res.json() as Promise<Alert[]>
}

/**
 * Recupera um alerta específico por ID.
 * Retorna null se não encontrado (404).
 */
export async function fetchAlert(alertId: string): Promise<Alert | null> {
  const res = await fetch(`${API_URL}/alerts/${encodeURIComponent(alertId)}`, {
    headers: buildHeaders(),
    cache: 'no-store',
  })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`/alerts/${alertId} retornou ${res.status}`)
  return res.json() as Promise<Alert>
}

/**
 * Retorna o último relatório de avaliação do modelo.
 * Endpoint público — não requer autenticação.
 */
export async function fetchMetrics(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_URL}/metrics`, {
    headers: buildHeaders(),
    next: { revalidate: 60 },
  })
  if (!res.ok) throw new Error(`/metrics retornou ${res.status}`)
  return res.json() as Promise<Record<string, unknown>>
}
