/**
 * StatusBadge — indicador de status online/offline da API.
 */

interface Props {
  online: boolean
}

export function StatusBadge({ online }: Props) {
  return (
    <div className={`flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full border ${
      online
        ? 'text-green-700 bg-green-50 border-green-200'
        : 'text-red-700 bg-red-50 border-red-200'
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${online ? 'bg-green-500' : 'bg-red-500'}`} />
      API {online ? 'online' : 'offline'}
    </div>
  )
}
