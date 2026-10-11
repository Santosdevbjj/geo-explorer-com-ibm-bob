import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Sentinel Dashboard',
  description: 'Intelligent DevSecOps Sentinel — alertas de segurança priorizados e explicáveis',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-sentinel-surface">
        {/* ── Header ──────────────────────────────────────────────────── */}
        <header className="bg-white border-b border-sentinel-border">
          <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-sentinel-accent font-bold text-lg tracking-tight">
                Sentinel
              </span>
              <span className="text-sentinel-muted text-xs border border-sentinel-border rounded px-1.5 py-0.5">
                v0.1.0
              </span>
            </div>
            <nav className="flex items-center gap-4 text-sm text-sentinel-muted">
              <a href="/" className="hover:text-sentinel-text transition-colors">
                Alertas
              </a>
              <a href="/metrics" className="hover:text-sentinel-text transition-colors">
                Métricas
              </a>
              <a
                href={`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/docs`}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-sentinel-text transition-colors"
              >
                API Docs ↗
              </a>
            </nav>
          </div>
        </header>

        {/* ── Conteúdo principal ───────────────────────────────────────── */}
        <main className="max-w-5xl mx-auto px-4 py-6">
          {children}
        </main>

        {/* ── Footer ──────────────────────────────────────────────────── */}
        <footer className="border-t border-sentinel-border mt-12 py-4 text-center text-xs text-sentinel-muted">
          Intelligent DevSecOps Sentinel ·{' '}
          <a
            href="https://github.com/Santosdevbjj/geo-explorer-com-ibm-bob"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-sentinel-text"
          >
            GitHub
          </a>
          {' · '}Score não é probabilidade calibrada — veja{' '}
          <a href="/metrics" className="underline hover:text-sentinel-text">
            model-card
          </a>
        </footer>
      </body>
    </html>
  )
}
