/**
 * Página de 404 personalizada.
 */

import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="sentinel-card text-center py-12 space-y-4">
      <div className="text-5xl font-bold text-sentinel-muted">404</div>
      <h2 className="font-semibold text-sentinel-text">Alerta não encontrado</h2>
      <p className="text-sm text-sentinel-muted">
        O alerta pode ter expirado (alertas não persistem entre reinicializações da API).
      </p>
      <Link
        href="/"
        className="inline-block mt-2 text-sm text-sentinel-accent hover:underline"
      >
        ← Voltar para a lista de alertas
      </Link>
    </div>
  )
}
