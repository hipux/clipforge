import { useEffect, useState } from 'react'
import axios from 'axios'
import { Cpu, HardDrive } from 'lucide-react'

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

  const used = status.vram_usage.allocated_gb
  const total = status.vram_usage.total_gb
  const pct = total > 0 ? (used / total) * 100 : 0

  return (
    <div className="flex items-center gap-3 px-3 py-1.5 rounded-lg bg-slate-800/50 border border-slate-700/50 text-sm">
      <div className={`w-2 h-2 rounded-full shrink-0 ${
        status.is_gpu ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
      }`} />
      <span className="text-slate-300 font-medium text-xs">
        {status.is_gpu ? 'GPU' : 'CPU'}
      </span>
      {status.is_gpu && total > 0 && (
        <>
          <div className="flex items-center gap-1.5">
            <div className="w-20 h-1.5 bg-slate-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-amber-400' : 'bg-violet-500'
                }`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-slate-500 text-xs tabular-nums">
              {used.toFixed(1)}/{total.toFixed(0)} GB
            </span>
          </div>
          {status.nvenc_available && (
            <span className="text-xs px-1.5 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 font-medium">NVENC</span>
          )}
        </>
      )}
    </div>
  )
}
