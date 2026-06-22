import { useEffect, useState } from 'react'
import axios from 'axios'

interface VRAMUsage {
  allocated_gb: number
  reserved_gb: number
  total_gb: number
  free_gb: number
}

interface GPUStatus {
  device: string
  is_gpu: boolean
  vram_usage: VRAMUsage
  nvenc_available: boolean
  loaded_models: string[]
}

export function GPUStatusIndicator() {
  const [status, setStatus] = useState<GPUStatus | null>(null)

  useEffect(() => {
    const fetchStatus = () => {
      axios.get('/api/gpu/status')
        .then(r => setStatus(r.data))
        .catch(() => {})
    }
    
    fetchStatus()
    const id = setInterval(fetchStatus, 5000)
    return () => clearInterval(id)
  }, [])

  if (!status) return null

  const used = status.vram_usage.reserved_gb
  const total = status.vram_usage.total_gb
  const pct = total > 0 ? (used / total) * 100 : 0

  return (
    <div className="flex items-center gap-3 px-4 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm">
      <div className={`w-2.5 h-2.5 rounded-full ${status.is_gpu ? 'bg-green-400 animate-pulse' : 'bg-yellow-400'}`} />
      <span className="text-zinc-200 font-medium">
        {status.is_gpu ? 'GPU' : 'CPU'} режим
      </span>
      {status.is_gpu && total > 0 && (
        <>
          <div className="flex items-center gap-2">
            <div className="w-24 h-2 bg-zinc-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-green-500'
                }`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-zinc-400 text-xs">
              {used.toFixed(1)}/{total.toFixed(0)} GB
            </span>
          </div>
          {status.nvenc_available && (
            <span className="text-green-400 text-xs">NVENC ✓</span>
          )}
        </>
      )}
    </div>
  )
}
