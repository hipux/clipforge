import { useEffect, useRef } from 'react'
import { X, Clock, TrendingUp, Check } from 'lucide-react'
import { MomentCandidate } from '../store/useAppStore'

interface MomentPreviewModalProps {
  moment: MomentCandidate
  isSelected: boolean
  onToggle: () => void
  onClose: () => void
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

function scoreColor(score: number): string {
  if (score >= 85) return 'text-emerald-400'
  if (score >= 70) return 'text-yellow-400'
  return 'text-orange-400'
}

export default function MomentPreviewModal({ moment, isSelected, onToggle, onClose }: MomentPreviewModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const duration = Math.max(0, moment.end - moment.start)
  // Preview endpoint cuts just this segment, so the clip starts at t=0.
  const src = `/api/preview/${moment.video_id}/segment?start=${moment.start}&end=${moment.end}`
  // score can arrive as either a fraction (0–1) or already a percent (0–100);
  // normalize to percent, matching MomentCard.
  const pct = moment.score <= 1 ? Math.round(moment.score * 100) : Math.round(moment.score)

  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="relative flex flex-col md:flex-row gap-5 max-w-3xl w-full bg-surface rounded-2xl border border-slate-200 shadow-2xl p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute -top-3 -right-3 w-9 h-9 rounded-full bg-slate-900 text-white flex items-center justify-center shadow-lg hover:bg-slate-700 transition-colors"
          aria-label="Close"
        >
          <X size={18} />
        </button>

        {/* Vertical player */}
        <div className="shrink-0 mx-auto">
          <video
            ref={videoRef}
            src={src}
            className="h-[60vh] max-h-[520px] aspect-[9/16] object-cover rounded-xl bg-black"
            controls
            autoPlay
            loop
            playsInline
          />
        </div>

        {/* Info panel */}
        <div className="flex flex-col gap-4 flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <TrendingUp size={20} className={scoreColor(pct)} />
            <span className={`text-3xl font-bold ${scoreColor(pct)}`}>
              {pct}%
            </span>
            <span className="text-sm text-slate-400">match</span>
          </div>

          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Clock size={14} />
            <span>{formatTime(moment.start)} – {formatTime(moment.end)}</span>
            <span className="text-slate-400">({Math.round(duration)}s)</span>
          </div>

          <div className="text-sm leading-relaxed text-slate-600 overflow-y-auto max-h-[40vh]">
            {moment.reason || 'No description available.'}
          </div>

          <button
            onClick={onToggle}
            className={`mt-auto inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-medium transition-all duration-200 ease-out active:scale-[0.98] ${
              isSelected
                ? 'bg-accent text-white hover:bg-accent/90 shadow-sm'
                : 'bg-surface-2 text-slate-700 border border-slate-200 hover:bg-slate-100 hover:border-slate-300'
            }`}
          >
            <Check size={18} className={`transition-transform duration-200 ${isSelected ? 'scale-100 rotate-0' : 'scale-75 rotate-[-12deg] opacity-80'}`} />
            {isSelected ? 'Selected for export' : 'Select for export'}
          </button>
        </div>
      </div>
    </div>
  )
}