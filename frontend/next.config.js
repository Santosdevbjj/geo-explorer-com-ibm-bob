/** @type {import('next').NextConfig} */
const nextConfig = {
  // API URL injetada em build time via NEXT_PUBLIC_API_URL
  // Em dev local: http://localhost:8000
  // Em produção Vercel: URL do deploy Python
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
  },
  // Desabilita telemetria do Next.js
  eslint: {
    ignoreDuringBuilds: false,
  },
}

module.exports = nextConfig
